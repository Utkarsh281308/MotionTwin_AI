"""Convert segmentation masks into centroid tracks.

SAM 3.1 already gives each object a persistent id across frames, so `masks_to_tracks`
is the main path. `greedy_track` is a fallback for detectors that return unlinked
per-frame detections.
"""
import numpy as np

from app.schemas.models import Track, TrackPoint


def mask_centroid(mask: np.ndarray) -> tuple[float, float] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def masks_to_tracks(frames: dict[int, dict[int, np.ndarray]], label: str = "object") -> list[Track]:
    """frames: {frame_index: {object_id: binary_mask}}"""
    points: dict[int, list[TrackPoint]] = {}
    for frame_idx in sorted(frames):
        for obj_id, mask in frames[frame_idx].items():
            c = mask_centroid(mask)
            if c is not None:
                points.setdefault(obj_id, []).append(TrackPoint(frame=frame_idx, x=c[0], y=c[1]))
    return [Track(track_id=i, label=label, points=p) for i, p in sorted(points.items())]


def greedy_track(
    detections: dict[int, list[tuple[float, float]]], max_dist: float = 50.0, max_gap: int = 5
) -> list[Track]:
    """Link per-frame centroids to the nearest live track (simple nearest-neighbour tracker)."""
    tracks: list[Track] = []
    live: list[Track] = []
    for frame_idx in sorted(detections):
        live = [t for t in live if frame_idx - t.points[-1].frame <= max_gap]
        taken: set[int] = set()
        for x, y in detections[frame_idx]:
            best, best_d = None, max_dist
            for i, t in enumerate(live):
                if i in taken:
                    continue
                last = t.points[-1]
                d = float(np.hypot(last.x - x, last.y - y))
                if d < best_d:
                    best, best_d = i, d
            if best is None:
                t = Track(track_id=len(tracks), points=[])
                tracks.append(t)
                live.append(t)
                best = len(live) - 1
            taken.add(best)
            live[best].points.append(TrackPoint(frame=frame_idx, x=x, y=y))
    return tracks
