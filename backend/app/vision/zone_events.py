"""Turn object tracks + process zones into enter/exit timestamps."""
from app.schemas.models import Point, Track, Zone, ZoneEvent


def point_in_polygon(x: float, y: float, polygon: list[Point]) -> bool:
    """Ray-casting test."""
    inside = False
    n = len(polygon)
    for i in range(n):
        a, b = polygon[i], polygon[(i + 1) % n]
        if (a.y > y) != (b.y > y):
            x_cross = a.x + (y - a.y) * (b.x - a.x) / (b.y - a.y)
            if x < x_cross:
                inside = not inside
    return inside


def extract_zone_events(
    tracks: list[Track], zones: list[Zone], fps: float, min_frames: int = 2
) -> list[ZoneEvent]:
    """One event per continuous stay of a track inside a zone.

    Stays shorter than `min_frames` are treated as noise (object just passing an edge).
    """
    events: list[ZoneEvent] = []
    for track in tracks:
        pts = sorted(track.points, key=lambda p: p.frame)
        if not pts:
            continue
        first_frame, last_frame = pts[0].frame, pts[-1].frame
        for zone in zones:
            start = last = None
            for p in pts:
                if point_in_polygon(p.x, p.y, zone.polygon):
                    if start is None:
                        start = p.frame
                    last = p.frame
                elif start is not None:
                    _close(events, track, zone, start, last, fps, min_frames, first_frame, last_frame)
                    start = None
            if start is not None:
                _close(events, track, zone, start, last, fps, min_frames, first_frame, last_frame)
    events.sort(key=lambda e: e.enter_time)
    return events


def _close(events, track, zone, start, last, fps, min_frames, first_frame, last_frame):
    if last - start + 1 < min_frames:
        return
    events.append(
        ZoneEvent(
            track_id=track.track_id,
            zone_id=zone.id,
            enter_time=start / fps,
            exit_time=last / fps,
            censored=start == first_frame or last == last_frame,
        )
    )
