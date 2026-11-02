"""How much can we trust a process model built from this video?

Produces per-station statistics, a summary of what was observed, and plain-language
notices (too short a clip, too few visits, zones where objects never stop, ...).
"""
import numpy as np

from app.schemas.models import ModelSummary, Notice, StationStats, Track, Zone, ZoneEvent

MIN_CLIP_SECONDS = 20
MIN_VISITS = 10  # complete visits per station for usable timing estimates
MIN_ARRIVALS = 10
STOP_SPEED = 0.03  # "at rest" = moving slower than 3% of the frame width per second
STOP_WINDOW = 0.5  # seconds over which speed is measured (smooths out detection jitter)
STOP_SHARE = 0.3  # a visit counts as a stop if the object is at rest for 30% of it


def _stopped(track: Track, event: ZoneEvent, fps: float, width: int) -> bool:
    pts = [p for p in track.points if event.enter_time * fps <= p.frame <= event.exit_time * fps]
    if len(pts) < 2:
        return False
    frames = np.array([p.frame for p in pts], dtype=float)
    xy = np.array([(p.x, p.y) for p in pts])
    window = max(1.0, STOP_WINDOW * fps)
    at_rest = []
    for i, f in enumerate(frames):
        j = int(np.searchsorted(frames, f + window))
        if j >= len(frames):
            break
        speed = np.hypot(*(xy[j] - xy[i])) / ((frames[j] - f) / fps)
        at_rest.append(speed < STOP_SPEED * width)
    return bool(at_rest) and np.mean(at_rest) >= STOP_SHARE


def assess(
    events: list[ZoneEvent], tracks: list[Track], zones: list[Zone], fps: float, width: int, clip_seconds: float
) -> tuple[ModelSummary, list[StationStats], list[Notice]]:
    ordered = sorted(zones, key=lambda z: z.order)
    by_id = {t.track_id: t for t in tracks}
    notices: list[Notice] = []

    stats = []
    for z in ordered:
        visits = [e for e in events if e.zone_id == z.id]
        complete = [e for e in visits if not e.censored and e.duration > 0]
        stopped = [_stopped(by_id[e.track_id], e, fps, width) for e in complete if e.track_id in by_id]
        stats.append(StationStats(
            zone_id=z.id,
            name=z.name,
            visits=len(visits),
            complete_visits=len(complete),
            mean_time=float(np.mean([e.duration for e in complete])) if complete else None,
            stopped_share=float(np.mean(stopped)) if stopped else None,
        ))

    first, last = ordered[0].id, ordered[-1].id
    summary = ModelSummary(
        clip_seconds=clip_seconds,
        tracked_ids=len(tracks),
        objects_entered=len({e.track_id for e in events if e.zone_id == first}),
        objects_completed=len({e.track_id for e in events if e.zone_id == last and not e.censored}),
    )

    if clip_seconds < MIN_CLIP_SECONDS:
        notices.append(Notice(level="warning", message=(
            f"The clip is only {clip_seconds:.1f} s long. Use 30–60 s so each station is visited "
            f"at least {MIN_VISITS} times.")))
    if summary.objects_entered < MIN_ARRIVALS:
        notices.append(Notice(level="warning", message=(
            f"Only {summary.objects_entered} objects reached '{ordered[0].name}', so the arrival "
            "rate is a rough estimate.")))
    for s in stats:
        if s.complete_visits < 3:
            notices.append(Notice(level="error", message=(
                f"'{s.name}' has only {s.complete_visits} complete visit(s). Its timing is a guess, "
                "and the confidence ranges below understate the real uncertainty.")))
        elif s.complete_visits < MIN_VISITS:
            notices.append(Notice(level="warning", message=(
                f"'{s.name}' has {s.complete_visits} complete visits (aim for {MIN_VISITS}+). "
                "Treat its timing as approximate.")))
        if s.stopped_share is not None and s.stopped_share < 0.2:
            notices.append(Notice(level="warning", message=(
                f"Objects rarely stop in '{s.name}' ({s.stopped_share:.0%} of visits). It looks like a "
                "transit segment rather than a work station, so its 'service time' is really travel time.")))
    if summary.tracked_ids > 1.5 * max(summary.objects_entered, 1) and summary.objects_entered:
        notices.append(Notice(level="info", message=(
            f"{summary.tracked_ids} tracker ids for {summary.objects_entered} objects entering the line: "
            "some objects were split into several ids or never reached the first station.")))
    return summary, stats, notices
