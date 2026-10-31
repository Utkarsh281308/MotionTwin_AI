import type { Session, Zone } from "../types";

// MVP: zones are rectangles edited with number inputs. TODO: drag-to-draw on the video frame.
interface Rect { x: number; y: number; w: number; h: number }

function toRect(z: Zone): Rect {
  const xs = z.polygon.map((p) => p.x);
  const ys = z.polygon.map((p) => p.y);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

function fromRect(r: Rect) {
  return [
    { x: r.x, y: r.y }, { x: r.x + r.w, y: r.y },
    { x: r.x + r.w, y: r.y + r.h }, { x: r.x, y: r.y + r.h },
  ];
}

interface Props { session: Session; zones: Zone[]; onChange: (zones: Zone[]) => void }

export default function ZoneEditor({ session, zones, onChange }: Props) {
  const update = (i: number, patch: Partial<Zone>) =>
    onChange(zones.map((z, j) => (j === i ? { ...z, ...patch } : z)));

  const updateRect = (i: number, key: keyof Rect, value: number) =>
    update(i, { polygon: fromRect({ ...toRect(zones[i]), [key]: value }) });

  const addZone = () => {
    const n = zones.length;
    onChange([...zones, {
      id: `Z${n + 1}`, name: `Station ${n + 1}`, capacity: 1, order: n,
      polygon: fromRect({ x: 50, y: 50, w: 60, h: 60 }),
    }]);
  };

  return (
    <div className="zone-editor">
      <svg viewBox={`0 0 ${session.width} ${session.height}`} className="frame">
        {session.tracks.map((t) => (
          <polyline key={t.track_id} className="track"
            points={t.points.map((p) => `${p.x},${p.y}`).join(" ")} />
        ))}
        {zones.map((z) => {
          const r = toRect(z);
          return (
            <g key={z.id}>
              <rect className="zone" x={r.x} y={r.y} width={r.w} height={r.h} />
              <text x={r.x} y={r.y - 4} className="zone-label">{z.name}</text>
            </g>
          );
        })}
      </svg>
      <table>
        <thead>
          <tr><th>Order</th><th>Name</th><th>x</th><th>y</th><th>w</th><th>h</th><th>Capacity</th><th /></tr>
        </thead>
        <tbody>
          {zones.map((z, i) => {
            const r = toRect(z);
            return (
              <tr key={z.id}>
                <td><input type="number" value={z.order} onChange={(e) => update(i, { order: +e.target.value })} /></td>
                <td><input value={z.name} onChange={(e) => update(i, { name: e.target.value })} /></td>
                {(["x", "y", "w", "h"] as const).map((k) => (
                  <td key={k}><input type="number" value={r[k]} onChange={(e) => updateRect(i, k, +e.target.value)} /></td>
                ))}
                <td><input type="number" min={1} value={z.capacity} onChange={(e) => update(i, { capacity: Math.max(1, +e.target.value) })} /></td>
                <td><button onClick={() => onChange(zones.filter((_, j) => j !== i))}>✕</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <button onClick={addZone}>+ Add zone</button>
    </div>
  );
}
