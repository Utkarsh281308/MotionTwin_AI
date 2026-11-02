"""Build a ProcessModel (arrivals + service times per station) from zone events."""
import numpy as np

TRAVEL_QUANTILE = 0.25  # travel time = the fastest quarter of observed transfers (see below)

from app.schemas.models import ProcessModel, StationModel, Zone, ZoneEvent


def build_process_model(events: list[ZoneEvent], zones: list[Zone], observed_duration: float) -> ProcessModel:
    ordered = sorted(zones, key=lambda z: z.order)
    if not ordered:
        raise ValueError("At least one zone is required")

    first = ordered[0]
    arrivals = np.sort([e.enter_time for e in events if e.zone_id == first.id])
    interarrivals = [float(d) for d in np.diff(arrivals) if d > 0]
    if len(interarrivals) < 2:
        raise ValueError(f"Not enough arrivals observed at '{first.name}' (need at least 3 objects)")

    stations = []
    for z in ordered:
        times = [e.duration for e in events if e.zone_id == z.id and not e.censored and e.duration > 0]
        if not times:
            raise ValueError(f"No complete visits observed at '{z.name}' - check the zone position")
        stations.append(StationModel(zone_id=z.id, name=z.name, capacity=z.capacity, service_times=times))

    # Travel between stations: per object, from leaving station i to entering station i+1.
    # The gap also contains any time spent queueing in front of station i+1, which the simulation
    # models itself, so we keep only the fastest transfers (objects that did not have to wait).
    transfers = []
    for a, b in zip(ordered, ordered[1:]):
        exits = {e.track_id: e.exit_time for e in events if e.zone_id == a.id and not e.censored}
        gaps = [e.enter_time - exits[e.track_id] for e in events
                if e.zone_id == b.id and e.track_id in exits and e.enter_time > exits[e.track_id]]
        if gaps:
            cutoff = float(np.quantile(gaps, TRAVEL_QUANTILE))
            gaps = [g for g in gaps if g <= cutoff]
        transfers.append(gaps or [0.0])

    last = ordered[-1]
    completed = len({e.track_id for e in events if e.zone_id == last.id and not e.censored})
    return ProcessModel(
        stations=stations,
        interarrival_times=interarrivals,
        transfer_times=transfers,
        observed_duration=observed_duration,
        observed_completed=completed,
    )
