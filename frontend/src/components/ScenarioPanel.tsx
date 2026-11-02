import { secs } from "../lib/format";
import type { ProcessModel, Scenario } from "../types";

interface Props {
  model: ProcessModel;
  scenario: Scenario;
  onChange: (s: Scenario) => void;
  onRun: (s: Scenario) => void;
  busy: boolean;
}

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

/** Station with the highest load (mean time / capacity): the natural place to add capacity. */
function mostLoaded(model: ProcessModel) {
  return model.stations.reduce((best, s) =>
    mean(s.service_times) / s.capacity > mean(best.service_times) / best.capacity ? s : best);
}

export function presets(model: ProcessModel): { key: string; label: string; scenario: Scenario }[] {
  const target = mostLoaded(model);
  return [
    { key: "A", label: "A · As observed", scenario: { name: "As observed", station_changes: [], arrival_rate_factor: 1 } },
    { key: "B", label: "B · Demand +50%", scenario: { name: "Demand +50%", station_changes: [], arrival_rate_factor: 1.5 } },
    {
      key: "C", label: `C · +1 capacity at ${target.name}`,
      scenario: {
        name: `+1 capacity at ${target.name}`, arrival_rate_factor: 1,
        station_changes: [{ zone_id: target.zone_id, capacity: target.capacity + 1, speed_factor: 1 }],
      },
    },
  ];
}

export default function ScenarioPanel({ model, scenario, onChange, onRun, busy }: Props) {
  const change = (zoneId: string) =>
    scenario.station_changes.find((c) => c.zone_id === zoneId) ?? { zone_id: zoneId, speed_factor: 1 };

  const setChange = (zoneId: string, patch: { capacity?: number; speed_factor?: number }) => {
    const others = scenario.station_changes.filter((c) => c.zone_id !== zoneId);
    onChange({ ...scenario, name: "Custom", station_changes: [...others, { ...change(zoneId), ...patch }] });
  };

  return (
    <div className="scenario">
      <div className="presets" role="group" aria-label="Scenario presets">
        {presets(model).map((p) => (
          <button key={p.key} className={`preset ${scenario.name === p.scenario.name ? "active" : ""}`}
            disabled={busy} onClick={() => { onChange(p.scenario); onRun(p.scenario); }}>
            {p.label}
          </button>
        ))}
      </div>

      <details>
        <summary>Custom scenario</summary>
        <table className="data">
          <thead>
            <tr><th>Station</th><th>Observed time</th><th>Capacity</th><th>Speed</th></tr>
          </thead>
          <tbody>
            {model.stations.map((s) => {
              const c = change(s.zone_id);
              return (
                <tr key={s.zone_id}>
                  <td>{s.name}</td>
                  <td className="num">{secs(mean(s.service_times))}</td>
                  <td><input type="number" min={1} value={c.capacity ?? s.capacity}
                    onChange={(e) => setChange(s.zone_id, { capacity: Math.max(1, +e.target.value || 1) })} /></td>
                  <td>
                    <input type="range" min={0.5} max={3} step={0.1} value={c.speed_factor}
                      aria-label={`${s.name} speed`}
                      onChange={(e) => setChange(s.zone_id, { speed_factor: +e.target.value })} />
                    <span className="num"> ×{c.speed_factor.toFixed(1)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <label className="inline">
          Arrival rate
          <input type="range" min={0.5} max={2} step={0.1} value={scenario.arrival_rate_factor}
            onChange={(e) => onChange({ ...scenario, name: "Custom", arrival_rate_factor: +e.target.value })} />
          <span className="num">×{scenario.arrival_rate_factor.toFixed(1)}</span>
          <span className="muted"> (observed: one every {secs(mean(model.interarrival_times))})</span>
        </label>
        <button disabled={busy} onClick={() => onRun(scenario)}>Run custom scenario</button>
      </details>
    </div>
  );
}
