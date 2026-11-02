import { useState } from "react";
import { secs } from "../lib/format";
import type { ZoneEvent, Zone } from "../types";

interface Props {
  events: ZoneEvent[];
  zones: Zone[];
  duration: number;
  time: number;
  onSeek: (t: number) => void;
}

const VB_W = 1000;
const LABEL_W = 130;
const ROW_H = 30;
const BAR_H = 14;
const AXIS_H = 22;

/** Every station visit on a time axis, synced with the video. Click a visit to jump to it. */
export default function EventTimeline({ events, zones, duration, time, onSeek }: Props) {
  const [hover, setHover] = useState<{ e: ZoneEvent; x: number; y: number } | null>(null);
  const plotW = VB_W - LABEL_W - 10;
  const x = (t: number) => LABEL_W + (t / duration) * plotW;
  const height = zones.length * ROW_H + AXIS_H;
  const tickStep = duration > 120 ? 30 : duration > 40 ? 10 : duration > 10 ? 5 : 1;
  const ticks = Array.from({ length: Math.floor(duration / tickStep) + 1 }, (_, i) => i * tickStep);
  const names = new Map(zones.map((z) => [z.id, z.name]));

  return (
    <div className="timeline">
      <svg viewBox={`0 0 ${VB_W} ${height}`} role="img"
        aria-label="Station visits over time. Each bar is one object inside one station.">
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={x(t)} x2={x(t)} y1={0} y2={height - AXIS_H} />
            <text className="tick" x={x(t)} y={height - 6} textAnchor="middle">{t}s</text>
          </g>
        ))}
        {zones.map((z, row) => {
          const y = row * ROW_H + (ROW_H - BAR_H) / 2;
          return (
            <g key={z.id}>
              <text className="row-label" x={LABEL_W - 10} y={y + BAR_H - 2} textAnchor="end">
                {row + 1}. {z.name.length > 16 ? `${z.name.slice(0, 15)}…` : z.name}
              </text>
              {events.filter((e) => e.zone_id === z.id).map((e, i) => (
                <rect key={`${e.track_id}-${i}`} className={`visit ${e.censored ? "censored" : ""}`}
                  x={x(e.enter_time)} y={y} rx={3}
                  width={Math.max(2, x(e.exit_time) - x(e.enter_time) - 2)} height={BAR_H}
                  onMouseEnter={(ev) => setHover({ e, x: ev.clientX, y: ev.clientY })}
                  onMouseMove={(ev) => setHover({ e, x: ev.clientX, y: ev.clientY })}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => onSeek(Math.max(0, e.enter_time - 0.5))} />
              ))}
            </g>
          );
        })}
        <line className="playhead" x1={x(time)} x2={x(time)} y1={0} y2={height - AXIS_H} />
      </svg>
      <div className="legend">
        <span><i className="swatch visit-swatch" /> complete visit (used for timings)</span>
        <span><i className="swatch censored-swatch" /> cut off by the clip edge (excluded)</span>
        <span className="muted">Click a visit to jump the video there.</span>
      </div>
      {hover && (
        <div className="tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>
          <b>Object #{hover.e.track_id}</b> · {names.get(hover.e.zone_id)}<br />
          {secs(hover.e.enter_time)} → {secs(hover.e.exit_time)} ({secs(hover.e.exit_time - hover.e.enter_time)})
          {hover.e.censored && <><br /><span className="muted">cut off, so not used for timings</span></>}
        </div>
      )}
    </div>
  );
}
