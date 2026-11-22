import type { Fact, Rate, Result, RunDetail } from "../api";
import { Cite } from "./Cite";
import { CHECK, LABELS } from "./FactsTable";
import { rateText } from "./rates";
import { StatusBadge } from "./StatusBadge";

const POLICY: Record<string, string> = {
  comprehensive: "Comprehensive",
  satp: "Stand-alone TP",
  saod: "Stand-alone OD",
};

/** The run's printed serial: the first block of its id, as on a pre-numbered schedule. */
export function serial(id: string): string {
  return `Run ${id.split("-")[0].toUpperCase()}`;
}

function Cell({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={label}
      className="flex flex-col gap-1 border-rule p-5 max-sm:border-b sm:border-r sm:last:border-r-0"
    >
      <h3 className="text-sm font-semibold text-ink-muted">{label}</h3>
      {children}
    </section>
  );
}

function RateCell({
  label,
  rate,
  resolved,
}: {
  label: string;
  rate: Rate | undefined;
  resolved: boolean;
}) {
  const has = rate?.applicable === true && rate.ratePercent !== null;
  // A refused run explains itself once, below the cells; a resolved one explains each rate here.
  const explain = has || rate?.applicable === false || resolved;
  return (
    <Cell label={label}>
      <p
        className={
          has
            ? "tabular text-rate font-bold"
            : "pt-2 text-2xl font-semibold text-ink-muted"
        }
      >
        {rateText(rate, resolved)}
      </p>
      {rate?.gridCitation && (
        <p>
          <Cite text={rate.gridCitation} />
        </p>
      )}
      {rate?.reason && explain && (
        <p className="text-sm text-ink-muted">{rate.reason}</p>
      )}
    </Cell>
  );
}

const camel = (s: string) =>
  s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());

/**
 * The engine's confidence reason in the reviewer's words: "weakest link: cc (verified one, page 1)"
 * becomes "Weakest link: Engine CC, read by one OCR engine (page 1)", with that fact's quote.
 */
export function confidenceText(
  reason: string,
  facts: Record<string, Fact>,
): { text: string; quote: string | null } {
  const m = /^weakest link: (\w+) \(([^,)]+)(?:, page (\d+))?\)(.*)$/s.exec(
    reason,
  );
  if (!m) return { text: reason, quote: null };
  const key = camel(m[1]);
  const raw = CHECK[m[2].replace(/ /g, "_")] ?? m[2];
  const check = raw.charAt(0).toLowerCase() + raw.slice(1);
  const how = /OCR/.test(check) ? `read by ${check}` : check;
  const page = m[3] ? ` (page ${m[3]})` : "";
  return {
    text: `Weakest link: ${LABELS[key] ?? m[1]}, ${how}${page}${m[4]}`,
    quote: facts[key]?.quote ?? null,
  };
}

function why(res: Result): string | null {
  if (res.status === "resolved") return null;
  const reasons = [res.rates.od, res.rates.tp]
    .filter((r) => r?.applicable === true && r.ratePercent === null)
    .map((r) => r?.reason)
    .filter((r): r is string => Boolean(r));
  return reasons[0] ?? res.trace.at(-1)?.decision ?? null;
}

function ConfidenceCell({ res }: { res: Result }) {
  const c = confidenceText(res.confidence.reason, res.facts);
  return (
    <Cell label="Confidence">
      <p className="pt-1 text-2xl font-semibold capitalize">
        {res.confidence.level}
      </p>
      <p className="text-sm text-ink-muted">{c.text}</p>
      {c.quote && (
        <p
          title={c.quote}
          className="rounded-sm bg-quote px-2 py-1 font-mono text-[0.8125rem] leading-snug text-ink-soft [overflow-wrap:anywhere]"
        >
          <span className="line-clamp-4">{c.quote}</span>
        </p>
      )}
    </Cell>
  );
}

/** The rate schedule: one security-banded panel holding the verdict, both rates and the confidence. */
export function RatesCard({
  run,
  res,
  printed,
}: {
  run: RunDetail;
  res: Result | null;
  printed: boolean;
}) {
  const insurer = res?.facts.insurer?.value;
  const policy = res?.facts.policyType?.value;
  const band = [
    "Rate schedule",
    insurer ? String(insurer) : null,
    policy ? (POLICY[String(policy)] ?? String(policy)) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const reason = res ? why(res) : null;
  return (
    <article
      aria-label="Rate schedule"
      className="overflow-hidden rounded-lg border border-guard bg-sheet shadow-[0_1px_2px_rgba(28,36,64,0.06),0_8px_24px_-12px_rgba(28,36,64,0.18)]"
    >
      <div
        className={`border-b border-guard bg-guard-tint ${printed ? "guard-band-print" : ""}`}
      >
        <div className="guard-band h-6" aria-hidden="true" />
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 px-5 pb-2 pt-1">
          <p className="font-semibold text-guard-deep">{band}</p>
          <p className="font-mono text-sm font-medium tracking-wide text-serial">
            {serial(run.id)}
          </p>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-[0.7fr_1.15fr_1.15fr_1fr]">
        <Cell label="Status">
          <p className="pt-1">
            <StatusBadge status={run.status} size="lg" />
          </p>
        </Cell>
        {res ? (
          <>
            <RateCell
              label="OD rate"
              rate={res.rates.od}
              resolved={res.status === "resolved"}
            />
            <RateCell
              label="TP rate"
              rate={res.rates.tp}
              resolved={res.status === "resolved"}
            />
            <ConfidenceCell res={res} />
          </>
        ) : (
          <>
            <Cell label="OD rate">
              <p className="pt-2 text-2xl font-semibold text-ink-muted">—</p>
            </Cell>
            <Cell label="TP rate">
              <p className="pt-2 text-2xl font-semibold text-ink-muted">—</p>
            </Cell>
            <Cell label="Confidence">
              <p className="pt-2 text-2xl font-semibold text-ink-muted">—</p>
            </Cell>
          </>
        )}
      </div>
      <p className="microprint" aria-hidden="true">
        {`BROKERAGE RATE AGENT ${serial(run.id).toUpperCase()} · `.repeat(40)}
      </p>
      {reason && (
        <section
          aria-label="Why there is no rate"
          className="border-t border-rule bg-sheet-wash px-5 py-4"
        >
          <h3 className="text-sm font-semibold text-ink-muted">
            Why there is no rate
          </h3>
          <p className="mt-1 max-w-[75ch]">{reason}</p>
        </section>
      )}
    </article>
  );
}
