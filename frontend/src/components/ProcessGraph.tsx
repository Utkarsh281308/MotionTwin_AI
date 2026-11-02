import { int, num, pct, secs } from "../lib/format";
import type { ModelResponse } from "../types";

function Tile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="tile" title={hint}>
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
    </div>
  );
}

/** The process MotionTwin inferred from the video: arrivals -> stations -> departures, with evidence. */
export default function ProcessGraph({ result, stale }: { result: ModelResponse; stale: boolean }) {
  const { summary, stations, model } = result;
  const gaps = model.interarrival_times;
  const meanGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;

  return (
    <div className={stale ? "stale" : ""}>
      <div className="tiles">
        <Tile label="Clip length" value={secs(summary.clip_seconds)} />
        <Tile label="Tracked IDs" value={int(summary.tracked_ids)}
          hint="Tracker identities. One object can receive several IDs if tracking is interrupted." />
        <Tile label="Objects entered" value={int(summary.objects_entered)} hint="Distinct objects seen in the first station" />
        <Tile label="Objects completed" value={int(summary.objects_completed)}
          hint="Distinct objects that fully passed the last station" />
      </div>

      <div className="flow" role="list" aria-label="Inferred process">
        <div className="node terminal" role="listitem">
          <div className="node-title">Arrivals</div>
          <div className="node-line">one every <b>{secs(meanGap)}</b></div>
          <div className="node-line muted">{gaps.length} gaps observed</div>
        </div>
        {stations.map((s, i) => {
          const transit = s.stopped_share !== null && s.stopped_share < 0.2;
          const thin = s.complete_visits < 10;
          return (
            <div key={s.zone_id} className="flow-step" role="listitem">
              <span className="arrow" aria-hidden>→</span>
              <div className={`node ${transit || thin ? "flagged" : ""}`}>
                <div className="node-title">{i + 1}. {s.name}</div>
                <div className="node-line">time here <b>{secs(s.mean_time)}</b></div>
                <div className="node-line">capacity {model.stations[i]?.capacity ?? "–"}</div>
                <div className={`node-line ${thin ? "warn-text" : "muted"}`}>
                  {thin && <span aria-hidden>⚠ </span>}{s.complete_visits} complete visits
                </div>
                <div className={`node-line ${transit ? "warn-text" : "muted"}`}
                  title="Share of visits where the object came to rest. Low = objects pass through (transit), not a work station.">
                  {transit && <span aria-hidden>⚠ </span>}
                  {s.stopped_share === null ? "stops: –" : `stops in ${pct(s.stopped_share)} of visits`}
                </div>
              </div>
            </div>
          );
        })}
        <div className="flow-step" role="listitem">
          <span className="arrow" aria-hidden>→</span>
          <div className="node terminal">
            <div className="node-title">Completed</div>
            <div className="node-line"><b>{model.observed_completed}</b> in {num(model.observed_duration, 0)} s</div>
          </div>
        </div>
      </div>
    </div>
  );
}
