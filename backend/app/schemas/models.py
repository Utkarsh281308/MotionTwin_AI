"""Shared data models for the whole pipeline: video -> tracks -> zone events -> process model -> simulation."""
from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float
    y: float


class Zone(BaseModel):
    """A processing station drawn on the video frame. Should cover the work spot, NOT the queue area."""
    id: str
    name: str
    polygon: list[Point] = Field(min_length=3)
    capacity: int = Field(default=1, ge=1)
    order: int = 0  # position in the process flow (0 = first station)


class TrackPoint(BaseModel):
    frame: int
    x: float  # object centroid in pixels
    y: float


class Track(BaseModel):
    track_id: int
    label: str = "object"
    points: list[TrackPoint]


class ZoneEvent(BaseModel):
    track_id: int
    zone_id: str
    enter_time: float  # seconds
    exit_time: float
    censored: bool = False  # object was already inside at track start, or still inside at track end

    @property
    def duration(self) -> float:
        return self.exit_time - self.enter_time


class StationModel(BaseModel):
    zone_id: str
    name: str
    capacity: int
    service_times: list[float]  # observed seconds per object


class ProcessModel(BaseModel):
    stations: list[StationModel]  # in flow order
    interarrival_times: list[float]
    observed_duration: float  # seconds of video
    observed_completed: int  # objects that finished the last station


class StationChange(BaseModel):
    zone_id: str
    capacity: int | None = Field(default=None, ge=1)
    speed_factor: float = Field(default=1.0, gt=0)  # 2.0 = processes twice as fast


class Scenario(BaseModel):
    name: str = "scenario"
    station_changes: list[StationChange] = []
    arrival_rate_factor: float = Field(default=1.0, gt=0)  # 1.5 = 50% more arrivals


class SimulationRequest(BaseModel):
    model: ProcessModel
    scenario: Scenario | None = None
    sim_time: float = Field(default=3600, gt=0)
    replications: int = Field(default=30, ge=2, le=500)
    seed: int = 42


class Estimate(BaseModel):
    mean: float
    ci_low: float  # 95% confidence interval across replications
    ci_high: float


class StationResult(BaseModel):
    zone_id: str
    name: str
    capacity: int
    utilisation: Estimate
    avg_queue_length: Estimate
    avg_wait: Estimate


class SimResult(BaseModel):
    name: str
    throughput_per_hour: Estimate
    avg_cycle_time: Estimate
    stations: list[StationResult]


class Comparison(BaseModel):
    observed_throughput_per_hour: float
    baseline: SimResult
    scenario: SimResult | None = None
    bottleneck_zone_id: str
    explanation: str
