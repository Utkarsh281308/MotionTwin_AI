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
    assert find_bottleneck(simulate(MODEL, sim_time=600, replications=5)).zone_id == "B"


def test_no_bottleneck_when_lightly_loaded():
    light = MODEL.model_copy(update={"interarrival_times": [20.0, 25.0, 30.0]})
    b = find_bottleneck(simulate(light, sim_time=1800, replications=5))
    assert b.zone_id is None and b.busiest_zone_id == "B"


def test_few_observations_give_wider_ranges():
    many = MODEL.model_copy(update={"stations": [
        s.model_copy(update={"service_times": s.service_times * 10}) for s in MODEL.stations]})
    one = MODEL.model_copy(update={"stations": [
        MODEL.stations[0].model_copy(update={"service_times": [1.0, 4.0]}), MODEL.stations[1]]})
    width = lambda r: r.stations[0].utilisation.ci_high - r.stations[0].utilisation.ci_low
    assert width(simulate(one, sim_time=600, replications=20)) > width(simulate(many, sim_time=600, replications=20))


def test_adding_capacity_at_bottleneck_helps():
    base = simulate(MODEL, sim_time=1800, replications=10)
    better = simulate(MODEL, Scenario(station_changes=[StationChange(zone_id="B", capacity=2)]),
                      sim_time=1800, replications=10)
    assert better.throughput_per_hour.mean > base.throughput_per_hour.mean
    assert better.stations[1].avg_queue_length.mean < base.stations[1].avg_queue_length.mean


def test_saturated_tie_goes_to_longest_queue():
    from app.schemas.models import Estimate, SimResult, StationResult
    e = lambda v: Estimate(mean=v, ci_low=v, ci_high=v)
    st = lambda zid, util, q: StationResult(zone_id=zid, name=zid, capacity=1, utilisation=e(util),
                                            avg_queue_length=e(q), avg_wait=e(0))
    r = SimResult(name="x", completed=e(0), throughput_per_hour=e(0), avg_cycle_time=e(0),
                  stations=[st("Scan", 1.0, 121), st("Pack", 0.995, 237)])
    b = find_bottleneck(r)
    assert b.zone_id == "Pack" and "Also saturated: 'Scan'" in b.reason
