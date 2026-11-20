import type { Status } from "../api";

const LABEL: Record<Status, string> = {
  queued: "Queued",
  processing: "Processing",
  resolved: "Resolved",
  unsupported: "Unsupported",
  ambiguous: "Ambiguous",
  failed: "Failed",
};

// Colour supports the text label; it is never the only carrier of meaning (ux-standards).
const TONE: Record<Status, string> = {
  queued: "bg-slate-100 text-slate-800 border-slate-300",
  processing: "bg-sky-50 text-sky-900 border-sky-300",
  resolved: "bg-emerald-50 text-emerald-900 border-emerald-300",
  unsupported: "bg-amber-50 text-amber-900 border-amber-300",
  ambiguous: "bg-violet-50 text-violet-900 border-violet-300",
  failed: "bg-rose-50 text-rose-900 border-rose-300",
};

export function statusLabel(status: Status): string {
  return LABEL[status] ?? status;
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={`inline-block rounded border px-2 py-0.5 text-sm font-medium ${TONE[status]}`}
    >
      {statusLabel(status)}
    </span>
  );
}
