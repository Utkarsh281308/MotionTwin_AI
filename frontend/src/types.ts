// Mirrors backend/app/schemas/models.py and backend/app/api/routes.py
export interface Point { x: number; y: number }
export interface Zone { id: string; name: string; polygon: Point[]; capacity: number; order: number }
export interface TrackPoint { frame: number; x: number; y: number }
export interface Track { track_id: number; label: string; points: TrackPoint[] }
export interface Session {
  id: string; fps: number; width: number; height: number; duration: number;
  video_path: string | null; playback_path: string | null;
  tracks: Track[]; zones: Zone[]; track_source: string;
}
export interface ZoneEvent { track_id: number; zone_id: string; enter_time: number; exit_time: number; censored: boolean }
export interface StationModel { zone_id: string; name: string; capacity: number; service_times: number[] }
export interface ProcessModel {
  stations: StationModel[]; interarrival_times: number[];
  observed_duration: number; observed_completed: number;
}
export interface Notice { level: "info" | "warning" | "error"; message: string }
export interface StationStats {
  zone_id: string; name: string; visits: number; complete_visits: number;
  mean_time: number | null; stopped_share: number | null;
}
export interface ModelSummary { clip_seconds: number; tracked_ids: number; objects_entered: number; objects_completed: number }
export interface ModelResponse {
  events: ZoneEvent[]; model: ProcessModel; summary: ModelSummary; stations: StationStats[]; notices: Notice[];
}
export interface StationChange { zone_id: string; capacity?: number | null; speed_factor: number }
export interface Scenario { name: string; station_changes: StationChange[]; arrival_rate_factor: number }
export interface Estimate { mean: number; ci_low: number; ci_high: number }
export interface StationResult {
  zone_id: string; name: string; capacity: number;
  utilisation: Estimate; avg_queue_length: Estimate; avg_wait: Estimate;
}
export interface SimResult {
  name: string; completed: Estimate; throughput_per_hour: Estimate; avg_cycle_time: Estimate; stations: StationResult[];
}
export interface Calibration { window_seconds: number; observed_completed: number; simulated_completed: Estimate; error_pct: number }
export interface Bottleneck { zone_id: string | null; busiest_zone_id: string; reason: string }
export interface Comparison {
  observed_throughput_per_hour: number; calibration: Calibration;
  baseline: SimResult; scenario: SimResult | null; scenario_changes: string[];
  bottleneck: Bottleneck; scenario_bottleneck: Bottleneck | null;
  notices: Notice[]; explanation: string;
}
export interface PreviewBox { x1: number; y1: number; x2: number; y2: number }
export interface Preview { frame: number; prompt: string; boxes: PreviewBox[] }
