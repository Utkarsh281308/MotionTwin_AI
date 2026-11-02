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
    """Link per-frame centroids into tracks (nearest-neighbour tracker).

    Each frame, all (track, detection) pairs are matched shortest-distance first, so a box
    stepping forward can't steal the id of the box right behind it.
    """
    tracks: list[Track] = []
    live: list[Track] = []
    for frame_idx in sorted(detections):
        live = [t for t in live if frame_idx - t.points[-1].frame <= max_gap]
        dets = detections[frame_idx]
        pairs = sorted(
            (float(np.hypot(t.points[-1].x - x, t.points[-1].y - y)), ti, di)
            for ti, t in enumerate(live)
            for di, (x, y) in enumerate(dets)
        )
        used_t, used_d = set(), set()
        for d, ti, di in pairs:
            if d > max_dist:
                break
            if ti in used_t or di in used_d:
                continue
            used_t.add(ti)
            used_d.add(di)
            live[ti].points.append(TrackPoint(frame=frame_idx, x=dets[di][0], y=dets[di][1]))
        for di, (x, y) in enumerate(dets):
            if di not in used_d:
                t = Track(track_id=len(tracks), points=[TrackPoint(frame=frame_idx, x=x, y=y)])
                tracks.append(t)
                live.append(t)
    return tracks


def split_at_jumps(tracks: list[Track], max_step: float = 60.0) -> list[Track]:
    """Cut a track wherever it jumps further than `max_step` px per frame.

    SAM can re-use an id for a different object (e.g. after one leaves the frame,
    or beyond its 16-object limit); the jump marks where one object ends and another begins.
    """
    out: list[Track] = []
    next_id = 0
    for t in tracks:
        pts = sorted(t.points, key=lambda p: p.frame)
        segment = pts[:1]
        for a, b in zip(pts, pts[1:]):
            gap = max(1, b.frame - a.frame)
            if np.hypot(b.x - a.x, b.y - a.y) > max_step * gap:
                out.append(Track(track_id=next_id, label=t.label, points=segment))
                next_id += 1
                segment = []
            segment.append(b)
        if segment:
            out.append(Track(track_id=next_id, label=t.label, points=segment))
            next_id += 1
    return out
