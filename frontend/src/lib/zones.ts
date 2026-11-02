import type { Point, Zone } from "../types";

export interface Rect { x: number; y: number; w: number; h: number }

export function toRect(z: Zone): Rect {
  const xs = z.polygon.map((p) => p.x);
  const ys = z.polygon.map((p) => p.y);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

export function fromRect(r: Rect): Point[] {
  const x = Math.round(r.x), y = Math.round(r.y), w = Math.round(r.w), h = Math.round(r.h);
  return [{ x, y }, { x: x + w, y }, { x: x + w, y: y + h }, { x, y: y + h }];
}

/** Keep `order` equal to the list position (1st station = 0). */
export const renumber = (zones: Zone[]) => zones.map((z, i) => ({ ...z, order: i }));
