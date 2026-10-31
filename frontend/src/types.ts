// Mirrors backend/app/schemas/models.py
export interface Point { x: number; y: number }
export interface Zone { id: string; name: string; polygon: Point[]; capacity: number; order: number }
export interface TrackPoint { frame: number; x: number; y: number }
export interface Track { track_id: number; label: string; points: TrackPoint[] }
export interface Session {
  id: string; fps: number; width: number; height: number; duration: number;
  video_path: string | null; tracks: Track[]; zones: Zone[];
}
export interface ZoneEvent { track_id: number; zone_id: string; enter_time: number; exit_time: number; censored: boolean }
export interface StationModel { zone_id: string; name: string; capacity: number; service_times: number[] }
export interface ProcessModel {
  stations: StationModel[]; interarrival_times: number[];
  observed_duration: number; observed_completed: number;
}
export interface StationChange { zone_id: string; capacity?: number | null; speed_factor: number }
export interface Scenario { name: string; station_changes: StationChange[]; arrival_rate_factor: number }
export interface Estimate { mean: number; ci_low: number; ci_high: number }
export interface StationResult {
  zone_id: string; name: string; capacity: number;
  utilisation: Estimate; avg_queue_length: Estimate; avg_wait: Estimate;
}
export interface SimResult { name: string; throughput_per_hour: Estimate; avg_cycle_time: Estimate; stations: StationResult[] }
export interface Comparison {
  observed_throughput_per_hour: number; baseline: SimResult; scenario: SimResult | null;
  bottleneck_zone_id: string; explanation: string;
}
