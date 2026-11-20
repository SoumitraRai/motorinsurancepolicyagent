import type { Rate } from "../api";

/** One rate as plain text: "12.5%", "Not applicable", "Not published" or "—" while unknown. */
export function rateText(rate: Rate | null | undefined): string {
  if (!rate || rate.applicable === null) return "—";
  if (rate.applicable === false) return "Not applicable";
  if (rate.ratePercent === null) return "Not published";
  return `${rate.ratePercent}%`;
}
