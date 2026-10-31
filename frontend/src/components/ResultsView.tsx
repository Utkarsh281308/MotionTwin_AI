import type { Comparison, Estimate, SimResult } from "../types";

const fmt = (e: Estimate, d = 1, pct = false) => {
  const k = pct ? 100 : 1, u = pct ? "%" : "";
  return `${(e.mean * k).toFixed(d)}${u} (${(e.ci_low * k).toFixed(d)}–${(e.ci_high * k).toFixed(d)})`;
};

function Bar({ value, max, label }: { value: number; max: number; label: string }) {
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar"><div style={{ width: `${(value / max) * 100}%` }} /></div>
      <span>{value.toFixed(0)}/h</span>
    </div>
  );
}

export default function ResultsView({ result }: { result: Comparison }) {
  const runs: SimResult[] = [result.baseline, ...(result.scenario ? [result.scenario] : [])];
  const max = Math.max(result.observed_throughput_per_hour, ...runs.map((r) => r.throughput_per_hour.mean));

  return (
    <div>
      <h3>Throughput</h3>
      <Bar label="Observed (video)" value={result.observed_throughput_per_hour} max={max} />
      {runs.map((r) => <Bar key={r.name} label={r.name} value={r.throughput_per_hour.mean} max={max} />)}

      <h3>Stations <small>(mean, 95% CI)</small></h3>
      <table>
        <thead>
          <tr><th>Run</th><th>Station</th><th>Cap.</th><th>Utilisation</th><th>Avg queue</th><th>Avg wait (s)</th></tr>
        </thead>
        <tbody>
          {runs.flatMap((r) => r.stations.map((s) => (
            <tr key={r.name + s.zone_id} className={s.zone_id === result.bottleneck_zone_id ? "bottleneck" : ""}>
              <td>{r.name}</td><td>{s.name}</td><td>{s.capacity}</td>
              <td>{fmt(s.utilisation, 0, true)}</td>
              <td>{fmt(s.avg_queue_length)}</td>
              <td>{fmt(s.avg_wait)}</td>
            </tr>
          )))}
        </tbody>
      </table>

      <h3>AI explanation</h3>
      <p className="explanation">{result.explanation}</p>
    </div>
  );
}
