import json
import shutil
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.ai import muse
from app.schemas.models import (
    Calibration,
    Comparison,
    ModelSummary,
    Notice,
    ProcessModel,
    SimulationRequest,
    StationStats,
    Track,
    Zone,
    ZoneEvent,
)
from app.simulation.data_quality import assess
from app.simulation.engine import describe_scenario, find_bottleneck, simulate
from app.simulation.model_builder import build_process_model
from app.vision import meta_sam
from app.vision.video_io import read_frame_jpeg, to_browser_mp4
from app.vision.zone_events import extract_zone_events

router = APIRouter(prefix="/api")

ROOT = Path(__file__).resolve().parents[3]
UPLOAD_DIR = ROOT / "backend" / "uploads"
DEMO_TRACKS = ROOT / "sample_data" / "ground_truth" / "demo_tracks.json"
DEMO_VIDEO = ROOT / "sample_data" / "videos" / "demo_parcel_line.mp4"
DEMO_SAM = ROOT / "sample_data" / "ground_truth" / "demo_sam_raw_frames.json"  # saved live SAM 3.1 run


class Session(BaseModel):
    id: str
    fps: float = 0
    width: int = 0
    height: int = 0
    duration: float = 0
    video_path: str | None = None  # original file (sent to SAM)
    playback_path: str | None = None  # H.264 copy for the browser
    tracks: list[Track] = []
    zones: list[Zone] = []
    track_source: str = ""  # where the tracks came from, shown in the UI


class ModelResponse(BaseModel):
    events: list[ZoneEvent]
    model: ProcessModel
    summary: ModelSummary
    stations: list[StationStats]
    notices: list[Notice]


class PreviewBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Preview(BaseModel):
    frame: int
    prompt: str
    boxes: list[PreviewBox]


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
    try:
        fps, width, height, duration = meta_sam.read_video_info(str(path))
    except ValueError as e:
        raise HTTPException(400, str(e))
    playback = path.with_name(f"{sid}_playback.mp4")
    try:
        to_browser_mp4(str(path), str(playback))
    except Exception:
        playback = path  # still usable for tracking; the browser may not be able to play it
    SESSIONS[sid] = Session(id=sid, fps=fps, width=width, height=height, duration=duration,
                            video_path=str(path), playback_path=str(playback))
    return SESSIONS[sid]


@router.get("/sessions/{session_id}/video")
def session_video(session_id: str):
    s = _get(session_id)
    if not s.playback_path:
        raise HTTPException(404, "No video for this session")
    return FileResponse(s.playback_path, media_type="video/mp4")


@router.get("/sessions/{session_id}/frame")
def session_frame(session_id: str, index: int = 0):
    s = _get(session_id)
    if not s.video_path:
        raise HTTPException(404, "No video for this session")
    return Response(read_frame_jpeg(s.video_path, index), media_type="image/jpeg")


@router.post("/sessions/{session_id}/preview", response_model=Preview)
def preview_prompt(session_id: str, prompt: str, frame: int = 0):
    """Run SAM on ONE frame (≈ $0.0025) so the user can check the prompt before tracking the video."""
    s = _get(session_id)
    if not s.video_path:
        raise HTTPException(404, "No video for this session")
    try:
        boxes = meta_sam.detect_boxes(read_frame_jpeg(s.video_path, frame), prompt)
    except meta_sam.SamNotConfigured as e:
        raise HTTPException(501, str(e))
    except Exception as e:
        raise HTTPException(502, f"SAM 3.1 request failed: {e}")
    return Preview(frame=frame, prompt=prompt, boxes=[PreviewBox(x1=b.left, y1=b.top, x2=b.right, y2=b.bottom)
                                                      for b in boxes])


@router.post("/sessions/{session_id}/track", response_model=Session)
def track_video(session_id: str, prompt: str = "brown box"):
    s = _get(session_id)
    if not s.video_path:
        raise HTTPException(400, "This session has no video")
    try:
        s.tracks = meta_sam.segment_and_track(s.video_path, prompt)
        s.track_source = f"SAM 3.1 (prompt '{prompt}')"
    except meta_sam.SamNotConfigured as e:
        raise HTTPException(501, str(e))
    except Exception as e:
        raise HTTPException(502, f"SAM 3.1 request failed: {e}")
    if not s.tracks:
        raise HTTPException(422, f"SAM found no '{prompt}' objects - try a different prompt")
    return s


@lru_cache(maxsize=1)
def _recorded_demo_tracks(_mtime: float) -> tuple[list[Track], str]:
    """Parse the saved SAM run once (Meta's parser takes ~30 ms/frame); re-parsed if the file changes."""
    saved = json.loads(DEMO_SAM.read_text())
    raw = {int(k): v for k, v in saved["raw"].items()}
    return meta_sam.tracks_from_frame_outputs(raw, saved["stride"], label=saved["prompt"]), saved["prompt"]


@router.post("/demo/load", response_model=Session)
def load_demo():
    data = json.loads(DEMO_TRACKS.read_text())
    sid = "demo-" + uuid.uuid4().hex[:6]
    video = str(DEMO_VIDEO) if DEMO_VIDEO.exists() else None
    source = "synthetic ground truth"
    if DEMO_SAM.exists():  # prefer the real SAM 3.1 output for this video (recorded once, replayed for free)
        tracks, prompt = _recorded_demo_tracks(DEMO_SAM.stat().st_mtime)
        data["tracks"] = [t.model_copy(deep=True) for t in tracks]
        source = f"SAM 3.1 (recorded run, prompt '{prompt}')"
    SESSIONS[sid] = Session(id=sid, video_path=video, playback_path=video, track_source=source, **data)
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
    if not s.zones:
        raise HTTPException(400, "Draw at least one station zone first")
    events = extract_zone_events(s.tracks, s.zones, s.fps)
    try:
        model = build_process_model(events, s.zones, s.duration)
    except ValueError as e:
        raise HTTPException(422, str(e))
    summary, stations, notices = assess(events, s.tracks, s.zones, s.fps, s.width, s.duration)
    return ModelResponse(events=events, model=model, summary=summary, stations=stations, notices=notices)


@router.post("/simulate", response_model=Comparison)
def run_simulation(req: SimulationRequest):
    m = req.model
    baseline = simulate(m, None, req.sim_time, req.replications, req.seed)
    changes = describe_scenario(m, req.scenario)
    scenario = simulate(m, req.scenario, req.sim_time, req.replications, req.seed) if req.scenario else None

    # Calibration: simulate exactly the video's window, starting empty, and compare with what we saw.
    window = simulate(m, None, m.observed_duration, req.replications, req.seed) if m.observed_duration else None
    calibration = Calibration(
        window_seconds=m.observed_duration,
        observed_completed=m.observed_completed,
        simulated_completed=window.completed if window else baseline.completed,
        error_pct=((window.completed.mean - m.observed_completed) / m.observed_completed
                   if window and m.observed_completed else 0.0),
    )
    notices = list(req.notices)
    if m.observed_completed and abs(calibration.error_pct) > 0.25:
        notices.append(Notice(level="warning", message=(
            f"The model does not reproduce the video well: it predicts {calibration.simulated_completed.mean:.1f} "
            f"completed objects in {m.observed_duration:.0f} s, but {m.observed_completed} were observed. "
            "Check the zones before trusting the scenarios.")))
    if req.scenario and not changes:
        notices.append(Notice(level="info", message="The scenario has no changes, so it matches the baseline."))

    observed = m.observed_completed / m.observed_duration * 3600 if m.observed_duration else 0.0
    bottleneck = find_bottleneck(baseline)
    scenario_bottleneck = find_bottleneck(scenario) if scenario else None
    return Comparison(
        observed_throughput_per_hour=observed,
        calibration=calibration,
        baseline=baseline,
        scenario=scenario,
        scenario_changes=changes,
        bottleneck=bottleneck,
        scenario_bottleneck=scenario_bottleneck,
        notices=notices,
        explanation=muse.explain(observed, calibration, baseline, scenario, changes,
                                 bottleneck, scenario_bottleneck, notices),
    )
