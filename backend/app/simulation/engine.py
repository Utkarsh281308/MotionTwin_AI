"""Discrete-event simulation of a serial process line (SimPy).

Arrival gaps and service times are resampled from the observed values (empirical
bootstrap). Each replication uses seed+i, and baseline/scenario share seeds
(common random numbers), so comparisons are deterministic and fair.
"""
import random

import numpy as np
import simpy

from app.schemas.models import Estimate, ProcessModel, Scenario, SimResult, StationResult

SAMPLE_INTERVAL = 1.0  # seconds between queue/utilisation samples


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

    stations = []
    for s in model.stations:
        ch = changes.get(s.zone_id)
        cap = ch.capacity if ch and ch.capacity else s.capacity
        stations.append({
            "model": s,
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
        for st in stations:
            arrive = env.now
            with st["res"].request() as req:
                yield req
                st["waits"].append(env.now - arrive)
                yield env.timeout(rng.choice(st["model"].service_times) / st["speed"])
        cycle_times.append(env.now - start)

    def source():
        while True:
            yield env.timeout(rng.choice(model.interarrival_times) / arrival_factor)
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
        throughput_per_hour=_estimate([r["throughput_per_hour"] for r in runs]),
        avg_cycle_time=_estimate([r["avg_cycle_time"] for r in runs]),
        stations=stations,
    )


def find_bottleneck(result: SimResult) -> str:
    return max(result.stations, key=lambda s: s.utilisation.mean).zone_id
