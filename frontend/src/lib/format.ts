import type { Estimate } from "../types";

export const num = (v: number, digits = 1) =>
  Number.isFinite(v) ? v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "–";
export const int = (v: number) => num(v, 0);
export const secs = (v: number | null | undefined) => (v == null ? "–" : `${num(v, v < 10 ? 2 : 1)} s`);
export const pct = (v: number) => `${Math.round(v * 100)}%`;
export const signedPct = (v: number) => `${v >= 0 ? "+" : "−"}${Math.abs(Math.round(v * 100))}%`;
export const range = (e: Estimate, f: (n: number) => string) => `${f(e.ci_low)}–${f(e.ci_high)}`;
