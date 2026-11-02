import type { Notice } from "../types";

const ICON = { error: "⛔", warning: "⚠", info: "ℹ" } as const;
const LABEL = { error: "Unreliable", warning: "Caution", info: "Note" } as const;

export default function Notices({ notices }: { notices: Notice[] }) {
  if (!notices.length) return null;
  const order = { error: 0, warning: 1, info: 2 };
  return (
    <ul className="notices">
      {[...notices].sort((a, b) => order[a.level] - order[b.level]).map((n, i) => (
        <li key={i} className={`notice ${n.level}`}>
          <span className="notice-tag"><span aria-hidden>{ICON[n.level]}</span> {LABEL[n.level]}</span>
          <span>{n.message}</span>
        </li>
      ))}
    </ul>
  );
}
