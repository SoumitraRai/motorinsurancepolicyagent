import type { Rate } from "../api";

/**
 * One rate as plain text: "12.5%", "Not applicable", "Not published" (a resolved run whose grid publishes
 * no rate for it), "No rate" (a refused run) or "—" while unknown.
 */
export function rateText(
  rate: Rate | null | undefined,
  resolved = true,
): string {
  if (!rate || rate.applicable === null) return "—";
  if (rate.applicable === false) return "Not applicable";
  if (rate.ratePercent === null) return resolved ? "Not published" : "No rate";
  return `${rate.ratePercent}%`;
}
