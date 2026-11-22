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
  queued: "bg-sheet-wash text-ink-muted border-rule-strong",
  processing: "bg-sheet-wash text-ink border-ink-muted",
  resolved: "bg-guard-tint text-guard-deep border-guard",
  unsupported: "bg-refuse-tint text-refuse border-refuse/50",
  ambiguous: "bg-warn-tint text-warn border-warn/50",
  failed: "bg-refuse-tint text-refuse border-refuse/50",
};

export function statusLabel(status: Status): string {
  return LABEL[status] ?? status;
}

export function StatusBadge({
  status,
  size = "sm",
}: {
  status: Status;
  size?: "sm" | "lg";
}) {
  const scale =
    size === "lg" ? "px-3 py-1 text-base" : "px-2 py-px text-[0.8125rem]";
  return (
    <span
      className={`inline-block whitespace-nowrap rounded border font-semibold ${scale} ${TONE[status]}`}
    >
      {statusLabel(status)}
    </span>
  );
}
