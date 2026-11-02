"""Discrete-event simulation of a serial process line (SimPy).

Arrival gaps and service times are resampled from the observed values (empirical
bootstrap). Each replication first draws its own bootstrap sample of the observations,
so the confidence intervals include the uncertainty of having seen only a few objects,
not just simulation noise. Each replication uses seed+i, and baseline/scenario share
seeds (common random numbers), so comparisons are deterministic and fair.
"""
import random

import numpy as np
import simpy

from app.schemas.models import Bottleneck, Estimate, ProcessModel, Scenario, SimResult, StationResult

SAMPLE_INTERVAL = 1.0  # seconds between queue/utilisation samples
BOTTLENECK_UTILISATION = 0.85  # a station this busy (or with a queue) constrains the line
BOTTLENECK_QUEUE = 1.0


def _estimate(values: list[float]) -> Estimate:
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean()) if len(arr) else 0.0
    if len(arr) < 2:
        return Estimate(mean=mean, ci_low=mean, ci_high=mean)
    half = 1.96 * float(arr.std(ddof=1)) / np.sqrt(len(arr))
    return Estimate(mean=mean, ci_low=mean - half, ci_high=mean + half)


def run_once(model: ProcessModel, scenario: Scenario | None, sim_time: float, seed: int) -> dict:
    rng = random.Random(seed)
    env = simpy.Environment()
    changes = {c.zone_id: c for c in scenario.station_changes} if scenario else {}
    arrival_factor = scenario.arrival_rate_factor if scenario else 1.0

    def bootstrap(values: list[float]) -> list[float]:
        return rng.choices(values, k=len(values))

    interarrivals = bootstrap(model.interarrival_times)
    transfers = [bootstrap(t) for t in model.transfer_times]
    stations = []
    for s in model.stations:
        ch = changes.get(s.zone_id)
        cap = ch.capacity if ch and ch.capacity else s.capacity
        stations.append({
            "name": s.name,
            "service_times": bootstrap(s.service_times),
            "cap": cap,
            "speed": ch.speed_factor if ch else 1.0,
            "res": simpy.Resource(env, capacity=cap),
            "waits": [],
            "busy_samples": [],
            "queue_samples": [],
        })
    cycle_times: list[float] = []

    def item():
        start = env.now
        for i, st in enumerate(stations):
            if i > 0 and i - 1 < len(transfers):  # walk/convey to the next station (no capacity limit)
                yield env.timeout(rng.choice(transfers[i - 1]))
            arrive = env.now
            with st["res"].request() as req:
                yield req
                st["waits"].append(env.now - arrive)
                yield env.timeout(rng.choice(st["service_times"]) / st["speed"])
        cycle_times.append(env.now - start)

    def source():
        while True:
            yield env.timeout(rng.choice(interarrivals) / arrival_factor)
            env.process(item())

    def monitor():
        while True:
            for st in stations:
                st["busy_samples"].append(st["res"].count / st["cap"])
                st["queue_samples"].append(len(st["res"].queue))
            yield env.timeout(SAMPLE_INTERVAL)

    env.process(source())
    env.process(monitor())
    env.run(until=sim_time)

    return {
        "completed": len(cycle_times),
        "throughput_per_hour": len(cycle_times) / sim_time * 3600,
        "avg_cycle_time": float(np.mean(cycle_times)) if cycle_times else 0.0,
        "stations": [
            {
                "cap": st["cap"],
                "utilisation": float(np.mean(st["busy_samples"])),
                "avg_queue_length": float(np.mean(st["queue_samples"])),
                "avg_wait": float(np.mean(st["waits"])) if st["waits"] else 0.0,
            }
            for st in stations
        ],
    }


def simulate(
    model: ProcessModel,
    scenario: Scenario | None = None,
    sim_time: float = 3600,
    replications: int = 30,
    seed: int = 42,
) -> SimResult:
    runs = [run_once(model, scenario, sim_time, seed + i) for i in range(replications)]
    stations = []
    for idx, s in enumerate(model.stations):
        per = [r["stations"][idx] for r in runs]
        stations.append(StationResult(
            zone_id=s.zone_id,
            name=s.name,
            capacity=per[0]["cap"],
            utilisation=_estimate([p["utilisation"] for p in per]),
            avg_queue_length=_estimate([p["avg_queue_length"] for p in per]),
            avg_wait=_estimate([p["avg_wait"] for p in per]),
        ))
    return SimResult(
        name=scenario.name if scenario else "baseline",
        completed=_estimate([r["completed"] for r in runs]),
        throughput_per_hour=_estimate([r["throughput_per_hour"] for r in runs]),
        avg_cycle_time=_estimate([r["avg_cycle_time"] for r in runs]),
        stations=stations,
    )


def find_bottleneck(result: SimResult) -> Bottleneck:
    """Evidence-based: only call a station a bottleneck if it is nearly always busy or has a queue.

    When several stations are (almost) equally busy, e.g. all saturated, the one with the longest
    queue is the constraint: work piles up in front of it.
    """
    top = max(s.utilisation.mean for s in result.stations)
    busiest = max((s for s in result.stations if s.utilisation.mean >= top - 0.02),
                  key=lambda s: s.avg_queue_length.mean)
    util, queue = busiest.utilisation.mean, busiest.avg_queue_length.mean
    if util >= BOTTLENECK_UTILISATION or queue >= BOTTLENECK_QUEUE:
        reason = f"'{busiest.name}' is busy {util:.0%} of the time with {queue:.1f} objects waiting on average"
        if util >= 0.98:
            reason += "; it cannot keep up, so its queue keeps growing"
        others = [s.name for s in result.stations if s is not busiest and s.utilisation.mean >= 0.98]
        if others:
            reason += f". Also saturated: {', '.join(repr(n) for n in others)}"
        return Bottleneck(zone_id=busiest.zone_id, busiest_zone_id=busiest.zone_id, reason=reason + ".")
    return Bottleneck(zone_id=None, busiest_zone_id=busiest.zone_id, reason=(
        f"No station is constrained: the busiest, '{busiest.name}', is busy {util:.0%} of the time "
        f"with {queue:.1f} objects waiting on average."))


def describe_scenario(model: ProcessModel, scenario: Scenario | None) -> list[str]:
    """Human-readable list of what the scenario changes (empty = identical to baseline)."""
    if scenario is None:
        return []
    names = {s.zone_id: s for s in model.stations}
    out = []
    if scenario.arrival_rate_factor != 1:
        out.append(f"arrivals x{scenario.arrival_rate_factor:g}")
    for c in scenario.station_changes:
        st = names.get(c.zone_id)
        if st is None:
            continue
        if c.capacity and c.capacity != st.capacity:
            out.append(f"'{st.name}' capacity {st.capacity} -> {c.capacity}")
        if c.speed_factor != 1:
            out.append(f"'{st.name}' speed x{c.speed_factor:g}")
    return out
