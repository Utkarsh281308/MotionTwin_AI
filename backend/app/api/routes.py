import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from app.ai import muse
from app.schemas.models import Comparison, ProcessModel, SimulationRequest, Track, Zone, ZoneEvent
from app.simulation.engine import find_bottleneck, simulate
from app.simulation.model_builder import build_process_model
from app.vision import meta_sam
from app.vision.zone_events import extract_zone_events

router = APIRouter(prefix="/api")

ROOT = Path(__file__).resolve().parents[3]
UPLOAD_DIR = ROOT / "backend" / "uploads"
DEMO_TRACKS = ROOT / "sample_data" / "ground_truth" / "demo_tracks.json"


class Session(BaseModel):
    id: str
    fps: float = 0
    width: int = 0
    height: int = 0
    duration: float = 0
    video_path: str | None = None
    tracks: list[Track] = []
    zones: list[Zone] = []


class ModelResponse(BaseModel):
    events: list[ZoneEvent]
    model: ProcessModel


SESSIONS: dict[str, Session] = {}  # in-memory for the MVP


def _get(session_id: str) -> Session:
    if session_id not in SESSIONS:
        raise HTTPException(404, "Session not found")
    return SESSIONS[session_id]


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/videos", response_model=Session)
def upload_video(file: UploadFile):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    sid = uuid.uuid4().hex[:8]
    path = UPLOAD_DIR / f"{sid}_{Path(file.filename or 'video.mp4').name}"
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    SESSIONS[sid] = Session(id=sid, video_path=str(path))
    return SESSIONS[sid]


@router.post("/sessions/{session_id}/track", response_model=Session)
def track_video(session_id: str, prompt: str = "parcel"):
    s = _get(session_id)
    try:
        s.tracks, s.fps = meta_sam.segment_and_track(s.video_path, prompt)
    except meta_sam.SamNotConfigured as e:
        raise HTTPException(501, str(e))
    return s


@router.post("/demo/load", response_model=Session)
def load_demo():
    data = json.loads(DEMO_TRACKS.read_text())
    sid = "demo-" + uuid.uuid4().hex[:6]
    SESSIONS[sid] = Session(id=sid, **data)
    return SESSIONS[sid]


@router.put("/sessions/{session_id}/zones", response_model=Session)
def set_zones(session_id: str, zones: list[Zone]):
    s = _get(session_id)
    s.zones = zones
    return s


@router.post("/sessions/{session_id}/model", response_model=ModelResponse)
def build_model(session_id: str):
    s = _get(session_id)
    if not s.tracks:
        raise HTTPException(400, "No tracks yet - run tracking or load the demo")
    events = extract_zone_events(s.tracks, s.zones, s.fps)
    try:
        model = build_process_model(events, s.zones, s.duration)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return ModelResponse(events=events, model=model)


@router.post("/simulate", response_model=Comparison)
def run_simulation(req: SimulationRequest):
    baseline = simulate(req.model, None, req.sim_time, req.replications, req.seed)
    scenario = simulate(req.model, req.scenario, req.sim_time, req.replications, req.seed) if req.scenario else None
    observed = req.model.observed_completed / req.model.observed_duration * 3600 if req.model.observed_duration else 0.0
    bottleneck = find_bottleneck(baseline)
    return Comparison(
        observed_throughput_per_hour=observed,
        baseline=baseline,
        scenario=scenario,
        bottleneck_zone_id=bottleneck,
        explanation=muse.explain(observed, baseline, scenario, bottleneck),
    )
