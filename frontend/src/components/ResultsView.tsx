import { useState } from "react";
import { int, num, pct, range, signedPct } from "../lib/format";
import type { Bottleneck, Comparison, Estimate, SimResult } from "../types";
import Notices from "./Notices";

function CalibrationCard({ result }: { result: Comparison }) {
  const c = result.calibration;
  const err = Math.abs(c.error_pct);
  const status = !c.observed_completed ? "warning" : err <= 0.15 ? "good" : err <= 0.25 ? "warning" : "critical";
  const label = { good: "Matches the video", warning: "Rough match", critical: "Does not match the video" }[status];
  const icon = { good: "✓", warning: "⚠", critical: "⛔" }[status];
  return (
    <div className={`calibration status-${status}`}>
      <div className="status-tag"><span aria-hidden>{icon}</span> {label}</div>
      <p>
        In the <b>{num(c.window_seconds, 0)} s</b> clip, <b>{c.observed_completed}</b> objects completed the line.
        Simulating the same window (starting empty), the model predicts <b>{num(c.simulated_completed.mean, 1)}</b>{" "}
        <span className="muted">(95% range {range(c.simulated_completed, (n) => num(n, 1))})</span>
        {c.observed_completed > 0 && <>, an error of <b>{signedPct(c.error_pct)}</b></>}.
      </p>
    </div>
  );
}

interface BarRow { key: string; label: string; est: Estimate | null; value: number; cls: string }

/** Horizontal bars with 95% range whiskers. One axis: objects per hour. */
function ThroughputChart({ rows }: { rows: BarRow[] }) {
  const [hover, setHover] = useState<{ row: BarRow; x: number; y: number } | null>(null);
  const max = Math.max(...rows.map((r) => r.est?.ci_high ?? r.value)) * 1.1 || 1;
  const W = 600, LABEL = 170, VALUE = 70, ROW = 34, BAR = 14;
  const short = (s: string) => (s.length > 24 ? `${s.slice(0, 23)}…` : s);
  const x = (v: number) => LABEL + (v / max) * (W - LABEL - VALUE);
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${rows.length * ROW + 6}`} role="img" aria-label="Throughput per hour">
        {rows.map((r, i) => {
          const y = i * ROW + (ROW - BAR) / 2;
          return (
            <g key={r.key} onMouseMove={(e) => setHover({ row: r, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => setHover(null)}>
              <rect className="hit" x={0} y={i * ROW} width={W} height={ROW} />
              <text className="row-label" x={LABEL - 10} y={y + BAR - 2} textAnchor="end">{short(r.label)}</text>
              <rect className={`bar ${r.cls}`} x={LABEL} y={y} width={Math.max(2, x(r.value) - LABEL)} height={BAR} rx={4} />
              {r.est && r.est.ci_high > r.est.ci_low && (
                <g className="whisker">
                  <line x1={x(r.est.ci_low)} x2={x(r.est.ci_high)} y1={y + BAR / 2} y2={y + BAR / 2} />
                  <line x1={x(r.est.ci_low)} x2={x(r.est.ci_low)} y1={y + 2} y2={y + BAR - 2} />
                  <line x1={x(r.est.ci_high)} x2={x(r.est.ci_high)} y1={y + 2} y2={y + BAR - 2} />
                </g>
              )}
              <text className="value" x={x(r.est?.ci_high ?? r.value) + 8} y={y + BAR - 2}>{int(r.value)}/h</text>
            </g>
          );
        })}
      </svg>
      {hover && (
        <div className="tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>
          <b>{hover.row.label}</b>: {int(hover.row.value)} objects/hour
          {hover.row.est && <><br /><span className="muted">95% range {range(hover.row.est, int)}</span></>}
          {!hover.row.est && <><br /><span className="muted">measured directly from the clip</span></>}
        </div>
      )}
    </div>
  );
}

function Meter({ value }: { value: number }) {
  const level = value >= 0.85 ? "serious" : value >= 0.6 ? "warning" : "ok";
  return (
    <span className="meter-wrap">
      <span className={`meter ${level}`}><span style={{ width: `${Math.min(100, value * 100)}%` }} /></span>
      <span className="num">{pct(value)}</span>
    </span>
  );
}

function Verdict({ title, b }: { title: string; b: Bottleneck }) {
  return (
    <div className={`verdict ${b.zone_id ? "constrained" : "clear"}`}>
      <span className="status-tag">{b.zone_id ? <><span aria-hidden>⚠</span> Bottleneck</> : <><span aria-hidden>✓</span> No bottleneck</>}</span>
      <span><b>{title}:</b> {b.reason}</span>
    </div>
  );
}

function StationTable({ baseline, scenario }: { baseline: SimResult; scenario: SimResult | null }) {
  return (
    <table className="data">
      <thead>
        <tr>
          <th>Station</th>
          <th>Busy · baseline</th>{scenario && <th>Busy · scenario</th>}
          <th className="num">Avg queue</th><th className="num">Avg wait</th>
        </tr>
      </thead>
      <tbody>
        {baseline.stations.map((s, i) => {
          const sc = scenario?.stations[i];
          return (
            <tr key={s.zone_id}>
              <td>{s.name} <span className="muted">×{s.capacity}{sc && sc.capacity !== s.capacity ? ` → ×${sc.capacity}` : ""}</span></td>
              <td><Meter value={s.utilisation.mean} /></td>
              {sc && <td><Meter value={sc.utilisation.mean} /></td>}
              <td className="num">{num(s.avg_queue_length.mean)}{sc && ` → ${num(sc.avg_queue_length.mean)}`}</td>
              <td className="num">{num(s.avg_wait.mean)} s{sc && ` → ${num(sc.avg_wait.mean)} s`}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function ResultsView({ result }: { result: Comparison }) {
  const { baseline, scenario } = result;
  const rows: BarRow[] = [
    { key: "obs", label: "Observed in clip", est: null, value: result.observed_throughput_per_hour, cls: "observed" },
    { key: "base", label: "Baseline model", est: baseline.throughput_per_hour, value: baseline.throughput_per_hour.mean, cls: "baseline" },
  ];
  if (scenario) rows.push({ key: "scen", label: scenario.name, est: scenario.throughput_per_hour,
    value: scenario.throughput_per_hour.mean, cls: "scenario" });

  return (
    <div className="results">
      <section className="card">
        <h3>1 · Does the model reproduce the video?</h3>
        <CalibrationCard result={result} />
      </section>

      <section className="card">
        <h3>2 · Throughput <span className="muted">(objects per hour, steady state · bars show 95% range)</span></h3>
        {scenario && (
          <p className="changes">Scenario: {result.scenario_changes.length ? result.scenario_changes.join(", ") : "no changes"}</p>
        )}
        <ThroughputChart rows={rows} />
        <p className="muted small">
          “Observed” counts completions in the short clip, which starts with an empty line; the model is run for an
          hour in steady state, so it is usually higher. Section 1 is the like-for-like check.
        </p>
      </section>

      <section className="card wide">
        <h3>3 · Where is the constraint?</h3>
        <Verdict title="Baseline" b={result.bottleneck} />
        {result.scenario_bottleneck && <Verdict title={scenario!.name} b={result.scenario_bottleneck} />}
        <StationTable baseline={baseline} scenario={scenario} />
      </section>

      <section className="card wide">
        <h3>4 · Explanation <span className="muted">(Muse Spark · uses only the numbers above)</span></h3>
        <p className="explanation">{result.explanation}</p>
        <Notices notices={result.notices} />
      </section>
    </div>
  );
}
