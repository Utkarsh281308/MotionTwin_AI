"""SAM 3.1 detection + tracking via Meta's Responses API.

Docs: https://dev.meta.ai/docs/sam/segmenting and /docs/sam/reading-segmentation

Default = FRAMES mode: sample frames (10/s), ask SAM to find every object in each still
image, and link them into tracks with our own tracker. Why not send the whole video?
Tested 2026-11-01 on the demo video: video mode tracks at most 16 objects per request and
re-uses ids when objects leave/enter, so with 21 parcels half the station visits were lost.
Per-image detection found every box exactly.

Prompt wording matters a lot: on the demo, "brown box" found all boxes, "parcel" found none,
"box" also matched the coloured station mats. Let users change it.

Output text is one line per frame: `<Nf>id<|box;...|><|mask;...|>,...` (images use `<0f>`),
parsed with Meta's official `meta-sam-parser`. Boxes are in source pixels; we use box centres.
"""
import base64
from concurrent.futures import ThreadPoolExecutor

import cv2
from meta_sam_parser import (
    CompletedOutcome,
    SegmentationBoxRecord,
    image_segmentation_format,
    video_segmentation_format,
)

from app.meta_client import MetaKeyMissing, get_client
from app.schemas.models import Track, TrackPoint
from app.vision.tracker import greedy_track, split_at_jumps

MODEL = "sam-3.1"
SAMPLE_FPS = 10  # frames per second sent to SAM; also sets the timing resolution (0.1s)
WORKERS = 8  # parallel image requests (limit is 3,000/min per team)


class SamNotConfigured(RuntimeError):
    pass


def _client():
    try:
        return get_client()
    except MetaKeyMissing as e:
        raise SamNotConfigured(str(e))


def read_video_info(video_path: str) -> tuple[float, int, int, float]:
    """(fps, width, height, duration_seconds) using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return fps, width, height, frames / fps


def _boxes(output_text: str, fmt) -> list[SegmentationBoxRecord]:
    parser = fmt.create_parser()
    parser.push(output_text)
    records = parser.finish(CompletedOutcome()).result.records
    return [r for r in records if isinstance(r, SegmentationBoxRecord)]


def _centre(box: SegmentationBoxRecord) -> tuple[float, float]:
    return (box.left + box.right) / 2, (box.top + box.bottom) / 2


# ---------- frames mode (default) ----------

def sample_frames(video_path: str, sample_fps: float = SAMPLE_FPS) -> tuple[int, dict[int, bytes]]:
    """(stride, {frame_index: jpeg_bytes}) for every `stride`-th frame."""
    fps = read_video_info(video_path)[0]
    stride = max(1, round(fps / sample_fps))
    cap = cv2.VideoCapture(video_path)
    frames, idx = {}, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % stride == 0:
            frames[idx] = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
        idx += 1
    cap.release()
    return stride, frames


def request_sam_image(jpeg: bytes, text_prompt: str) -> str:
    """SAM's raw text output for one image (billed per image)."""
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    response = _client().responses.create(
        model=MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": text_prompt},
                {"type": "input_image", "image_url": url},
            ],
        }],
    )
    return response.output_text


def detect_boxes(jpeg: bytes, text_prompt: str) -> list[SegmentationBoxRecord]:
    """Boxes SAM finds in one image (used for the prompt preview)."""
    return _boxes(request_sam_image(jpeg, text_prompt), image_segmentation_format())


def request_sam_frames(video_path: str, text_prompt: str, sample_fps: float = SAMPLE_FPS) -> tuple[int, dict[int, str]]:
    """(stride, {frame_index: raw SAM output}) for the sampled frames."""
    stride, frames = sample_frames(video_path, sample_fps)
    _client()  # fail fast if the key is missing
    with ThreadPoolExecutor(WORKERS) as pool:
        outputs = pool.map(lambda jpeg: request_sam_image(jpeg, text_prompt), frames.values())
        return stride, dict(zip(frames.keys(), outputs))


def tracks_from_frame_outputs(raw: dict[int, str], stride: int, label: str = "object") -> list[Track]:
    detections = {
        frame: [_centre(b) for b in _boxes(text, image_segmentation_format())]
        for frame, text in raw.items()
    }
    # objects move at most ~60px per frame; allow a couple of missed detections
    tracks = greedy_track(detections, max_dist=60.0 * stride, max_gap=3 * stride)
    for t in tracks:
        t.label = label
    return tracks


# ---------- video mode (kept for comparison; max 16 objects, ids get re-used) ----------

def parse_sam_output(output_text: str, label: str = "object") -> list[Track]:
    """Turn SAM's per-frame video text into centroid tracks (one Track per object id)."""
    points: dict[str, list[TrackPoint]] = {}
    for rec in _boxes(output_text, video_segmentation_format()):
        if rec.frame is not None:
            x, y = _centre(rec)
            points.setdefault(rec.object_id, []).append(TrackPoint(frame=rec.frame.frame_index, x=x, y=y))
    tracks = []
    for i, (obj_id, pts) in enumerate(points.items()):
        track_id = int(obj_id) if obj_id.isdigit() else i
        tracks.append(Track(track_id=track_id, label=label, points=sorted(pts, key=lambda p: p.frame)))
    return split_at_jumps(tracks)


def request_sam_video(video_path: str, text_prompt: str) -> str:
    """Upload the video and return SAM's raw per-frame text output (billed per frame)."""
    client = _client()
    with open(video_path, "rb") as f:
        uploaded = client.files.create(file=f, purpose="user_data")
    response = client.responses.create(
        model=MODEL,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": text_prompt},
                {"type": "input_video", "file_id": uploaded.id},
            ],
        }],
    )
    return response.output_text


# ---------- entry point used by the API ----------

def segment_and_track(video_path: str, text_prompt: str = "brown box") -> list[Track]:
    """Track every object matching `text_prompt` (a short noun phrase) through the video."""
    stride, raw = request_sam_frames(video_path, text_prompt)
    return tracks_from_frame_outputs(raw, stride, label=text_prompt)
