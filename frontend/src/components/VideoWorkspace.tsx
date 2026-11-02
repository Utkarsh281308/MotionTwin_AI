import { useMemo, useRef, useState, type PointerEvent, type RefObject } from "react";
import { fromRect, renumber, toRect, type Rect } from "../lib/zones";
import type { PreviewBox, Session, Track, Zone } from "../types";

interface Props {
  session: Session;
  videoUrl: string | null;
  videoRef: RefObject<HTMLVideoElement>;
  time: number;
  zones: Zone[];
  onZonesChange: (zones: Zone[]) => void;
  selectedZoneId: string | null;
  onSelectZone: (id: string | null) => void;
  drawing: boolean;
  onDrawingDone: () => void;
  previewBoxes: PreviewBox[];
}

type Drag =
  | { kind: "draw"; start: { x: number; y: number }; rect: Rect }
  | { kind: "move"; id: string; offset: { x: number; y: number } }
  | { kind: "resize"; id: string };

/** Object positions per frame, for drawing live markers. */
function useFrameIndex(tracks: Track[]) {
  return useMemo(() => {
    const byFrame = new Map<number, { id: number; x: number; y: number }[]>();
    for (const t of tracks) {
      for (const p of t.points) {
        const list = byFrame.get(p.frame) ?? [];
        list.push({ id: t.track_id, x: p.x, y: p.y });
        byFrame.set(p.frame, list);
      }
    }
    return { byFrame, frames: [...byFrame.keys()].sort((a, b) => a - b) };
  }, [tracks]);
}

function nearestFrame(frames: number[], target: number) {
  let lo = 0, hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid] <= target) lo = mid; else hi = mid - 1;
  }
  return frames[lo];
}

export default function VideoWorkspace(props: Props) {
  const { session, videoUrl, videoRef, time, zones, onZonesChange, selectedZoneId, onSelectZone,
    drawing, onDrawingDone, previewBoxes } = props;
  const svgRef = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const { byFrame, frames } = useFrameIndex(session.tracks);

  const W = session.width || 640, H = session.height || 360;
  const unit = W / 640; // scale strokes and labels with the video resolution

  const frame = Math.round(time * session.fps);
  const shownFrame = frames.length ? nearestFrame(frames, frame) : undefined;
  const markers = shownFrame !== undefined && frame - shownFrame <= session.fps ? byFrame.get(shownFrame) ?? [] : [];

  const toVideo = (e: PointerEvent) => {
    const m = svgRef.current!.getScreenCTM()!.inverse();
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m);
    return { x: Math.max(0, Math.min(W, p.x)), y: Math.max(0, Math.min(H, p.y)) };
  };

  const updateZone = (id: string, rect: Rect) =>
    onZonesChange(zones.map((z) => (z.id === id ? { ...z, polygon: fromRect(rect) } : z)));

  const onDown = (e: PointerEvent) => {
    if (!drawing) return;
    const p = toVideo(e);
    svgRef.current!.setPointerCapture(e.pointerId);
    setDrag({ kind: "draw", start: p, rect: { x: p.x, y: p.y, w: 0, h: 0 } });
  };

  const onZoneDown = (e: PointerEvent, z: Zone, kind: "move" | "resize") => {
    if (drawing) return;
    e.stopPropagation();
    onSelectZone(z.id);
    // capture on the zone itself: the overlay ignores the pointer (so video controls work),
    // but captured events still bubble up to the svg handlers
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    const p = toVideo(e), r = toRect(z);
    setDrag(kind === "move" ? { kind, id: z.id, offset: { x: p.x - r.x, y: p.y - r.y } } : { kind, id: z.id });
  };

  const onMove = (e: PointerEvent) => {
    if (!drag) return;
    const p = toVideo(e);
    if (drag.kind === "draw") {
      const { start } = drag;
      setDrag({ ...drag, rect: { x: Math.min(start.x, p.x), y: Math.min(start.y, p.y),
        w: Math.abs(p.x - start.x), h: Math.abs(p.y - start.y) } });
    } else {
      const z = zones.find((zz) => zz.id === drag.id);
      if (!z) return;
      const r = toRect(z);
      if (drag.kind === "move") {
        updateZone(z.id, { ...r, x: Math.min(W - r.w, Math.max(0, p.x - drag.offset.x)),
          y: Math.min(H - r.h, Math.max(0, p.y - drag.offset.y)) });
      } else {
        updateZone(z.id, { ...r, w: Math.max(8 * unit, p.x - r.x), h: Math.max(8 * unit, p.y - r.y) });
      }
    }
  };

  const onUp = () => {
    if (drag?.kind === "draw") {
      const { rect } = drag;
      if (rect.w > 8 * unit && rect.h > 8 * unit) {
        const id = `Z${Date.now().toString(36)}`;
        onZonesChange(renumber([...zones, { id, name: `Station ${zones.length + 1}`, capacity: 1, order: 0,
          polygon: fromRect(rect) }]));
        onSelectZone(id);
      }
      onDrawingDone();
    }
    setDrag(null);
  };

  return (
    <div className="video-frame" style={{ aspectRatio: `${W} / ${H}` }}>
      {videoUrl ? (
        <video ref={videoRef} src={videoUrl} controls={!drawing} muted playsInline preload="auto" />
      ) : (
        <div className="video-placeholder">No video for this session</div>
      )}
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none"
        className={`overlay ${drawing ? "drawing" : ""}`}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}>
        {session.tracks.map((t) => (
          <polyline key={t.track_id} className="trail" strokeWidth={1.5 * unit}
            points={t.points.map((p) => `${p.x},${p.y}`).join(" ")} />
        ))}
        {zones.map((z, i) => {
          const r = toRect(z);
          const selected = z.id === selectedZoneId;
          return (
            <g key={z.id} className={`zone ${selected ? "selected" : ""}`}>
              <rect x={r.x} y={r.y} width={r.w} height={r.h} strokeWidth={(selected ? 3 : 2) * unit}
                onPointerDown={(e) => onZoneDown(e, z, "move")} />
              <text x={r.x} y={r.y - 5 * unit} fontSize={13 * unit}>{i + 1}. {z.name}</text>
              {selected && (
                <rect className="handle" x={r.x + r.w - 5 * unit} y={r.y + r.h - 5 * unit}
                  width={10 * unit} height={10 * unit} onPointerDown={(e) => onZoneDown(e, z, "resize")} />
              )}
            </g>
          );
        })}
        {previewBoxes.map((b, i) => (
          <rect key={i} className="preview-box" x={b.x1} y={b.y1} width={b.x2 - b.x1} height={b.y2 - b.y1}
            strokeWidth={2 * unit} strokeDasharray={`${5 * unit} ${3 * unit}`} />
        ))}
        {markers.map((m) => (
          <g key={m.id} className="marker">
            <circle cx={m.x} cy={m.y} r={6 * unit} strokeWidth={2 * unit} />
            <text x={m.x + 8 * unit} y={m.y - 8 * unit} fontSize={11 * unit}>#{m.id}</text>
          </g>
        ))}
        {drag?.kind === "draw" && (
          <rect className="draft" x={drag.rect.x} y={drag.rect.y} width={drag.rect.w} height={drag.rect.h}
            strokeWidth={2 * unit} />
        )}
      </svg>
    </div>
  );
}
