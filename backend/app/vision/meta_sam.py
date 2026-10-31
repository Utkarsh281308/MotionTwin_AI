"""SAM 3.1 video segmentation + tracking client.

TODO: implement against Meta's official SAM 3.1 docs (Meta Model API or local weights).
Expected output shape: {frame_index: {object_id: binary_mask}} -> pass to
tracker.masks_to_tracks().
"""
import os

from app.schemas.models import Track
from app.vision.tracker import masks_to_tracks  # noqa: F401  (used once implemented)

META_API_KEY = os.getenv("META_API_KEY")


class SamNotConfigured(RuntimeError):
    pass


def segment_and_track(video_path: str, text_prompt: str = "parcel") -> tuple[list[Track], float]:
    """Return (tracks, fps) for objects matching `text_prompt` in the video."""
    raise SamNotConfigured(
        "SAM 3.1 integration not implemented yet. Use the demo data (POST /api/demo/load) for now."
    )
