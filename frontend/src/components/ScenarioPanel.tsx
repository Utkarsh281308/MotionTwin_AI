import type { ProcessModel, Scenario } from "../types";

interface Props { model: ProcessModel; scenario: Scenario; onChange: (s: Scenario) => void }

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

export default function ScenarioPanel({ model, scenario, onChange }: Props) {
  const change = (zoneId: string) =>
    scenario.station_changes.find((c) => c.zone_id === zoneId) ?? { zone_id: zoneId, speed_factor: 1 };

  const setChange = (zoneId: string, patch: { capacity?: number; speed_factor?: number }) => {
    const others = scenario.station_changes.filter((c) => c.zone_id !== zoneId);
    onChange({ ...scenario, station_changes: [...others, { ...change(zoneId), ...patch }] });
  };

  return (
    <div>
      <label>Scenario name{" "}
        <input value={scenario.name} onChange={(e) => onChange({ ...scenario, name: e.target.value })} />
      </label>
      <table>
        <thead>
          <tr><th>Station</th><th>Observed visits</th><th>Mean time (s)</th><th>Capacity</th><th>Speed ×</th></tr>
        </thead>
        <tbody>
          {model.stations.map((s) => {
            const c = change(s.zone_id);
            return (
              <tr key={s.zone_id}>
                <td>{s.name}</td>
                <td>{s.service_times.length}</td>
                <td>{mean(s.service_times).toFixed(2)}</td>
                <td><input type="number" min={1} value={c.capacity ?? s.capacity}
                  onChange={(e) => setChange(s.zone_id, { capacity: Math.max(1, +e.target.value) })} /></td>
                <td>
                  <input type="range" min={0.5} max={3} step={0.1} value={c.speed_factor}
                    onChange={(e) => setChange(s.zone_id, { speed_factor: +e.target.value })} />
                  {c.speed_factor.toFixed(1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <label>Arrival rate ×{" "}
        <input type="range" min={0.5} max={2} step={0.1} value={scenario.arrival_rate_factor}
          onChange={(e) => onChange({ ...scenario, arrival_rate_factor: +e.target.value })} />
        {scenario.arrival_rate_factor.toFixed(1)}
        {" "}(observed mean gap {mean(model.interarrival_times).toFixed(2)}s)
      </label>
    </div>
  );
}
