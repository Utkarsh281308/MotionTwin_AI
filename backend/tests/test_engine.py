from app.schemas.models import ProcessModel, Scenario, StationChange, StationModel
from app.simulation.engine import find_bottleneck, simulate

MODEL = ProcessModel(
    stations=[
        StationModel(zone_id="A", name="A", capacity=1, service_times=[2.0, 2.5, 3.0]),
        StationModel(zone_id="B", name="B", capacity=1, service_times=[3.5, 4.0]),
    ],
    interarrival_times=[2.5, 3.0, 3.5],
    observed_duration=60,
    observed_completed=15,
)


def test_deterministic_with_same_seed():
    a = simulate(MODEL, sim_time=600, replications=5, seed=1)
    b = simulate(MODEL, sim_time=600, replications=5, seed=1)
    assert a == b


def test_bottleneck_is_slowest_station():
    assert find_bottleneck(simulate(MODEL, sim_time=600, replications=5)) == "B"


def test_adding_capacity_at_bottleneck_helps():
    base = simulate(MODEL, sim_time=1800, replications=10)
    better = simulate(MODEL, Scenario(station_changes=[StationChange(zone_id="B", capacity=2)]),
                      sim_time=1800, replications=10)
    assert better.throughput_per_hour.mean > base.throughput_per_hour.mean
    assert better.stations[1].avg_queue_length.mean < base.stations[1].avg_queue_length.mean
