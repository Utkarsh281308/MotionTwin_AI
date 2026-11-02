import { renumber } from "../lib/zones";
import type { Zone } from "../types";

interface Props {
  zones: Zone[];
  onChange: (zones: Zone[]) => void;
  selectedZoneId: string | null;
  onSelect: (id: string | null) => void;
}

/** Stations in process order. Draw/move/resize happens on the video; names, capacity and order here. */
export default function ZoneList({ zones, onChange, selectedZoneId, onSelect }: Props) {
  const update = (id: string, patch: Partial<Zone>) => onChange(zones.map((z) => (z.id === id ? { ...z, ...patch } : z)));
  const move = (i: number, d: number) => {
    const next = [...zones];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    onChange(renumber(next));
  };

  if (!zones.length) return <p className="muted">No stations yet. Click “Draw station”, then drag a box over a work spot.</p>;

  return (
    <ol className="zone-list">
      {zones.map((z, i) => (
        <li key={z.id} className={z.id === selectedZoneId ? "selected" : ""} onClick={() => onSelect(z.id)}>
          <span className="step">{i + 1}</span>
          <input aria-label="Station name" value={z.name} onChange={(e) => update(z.id, { name: e.target.value })} />
          <label title="Workers or machines that can process objects in parallel">
            capacity
            <input type="number" min={1} value={z.capacity}
              onChange={(e) => update(z.id, { capacity: Math.max(1, +e.target.value || 1) })} />
          </label>
          <button className="icon" title="Move earlier" disabled={i === 0} onClick={() => move(i, -1)}>↑</button>
          <button className="icon" title="Move later" disabled={i === zones.length - 1} onClick={() => move(i, 1)}>↓</button>
          <button className="icon danger" title="Delete station"
            onClick={() => { onChange(renumber(zones.filter((zz) => zz.id !== z.id))); onSelect(null); }}>✕</button>
        </li>
      ))}
    </ol>
  );
}
