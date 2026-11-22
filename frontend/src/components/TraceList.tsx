import type { TraceStep } from "../api";
import { Cite, citedPage } from "./Cite";

const KIND: Record<string, string> = {
  select: "Grid",
  date: "Dates",
  business_type: "Business type",
  map: "Mapping",
  match: "Row",
  exception: "Note",
  note: "Note",
  broker_bonus: "Broker bonus",
  result: "Result",
};

/** The engine's reasoning, one numbered step per decision, each with the citations it rests on. */
export function TraceList({
  steps,
  onOpenPage,
}: {
  steps: TraceStep[];
  onOpenPage?: (page?: number) => void;
}) {
  if (steps.length === 0)
    return <p className="text-ink-muted">No decision steps were recorded.</p>;
  return (
    <ol className="divide-y divide-rule border-y border-rule">
      {steps.map((s) => (
        <li
          key={s.step}
          className={`grid gap-x-6 gap-y-2 py-4 md:grid-cols-[2.5rem_7.5rem_minmax(0,1fr)_minmax(0,22rem)] ${s.warnings?.length ? "bg-warn-tint/60" : ""}`}
        >
          <span className="tabular font-mono text-sm text-serial md:pl-2 md:pt-0.5">
            {String(s.step).padStart(2, "0")}
          </span>
          <span className="text-sm font-semibold text-ink-muted md:pt-0.5">
            {KIND[s.kind] ?? s.kind}
          </span>
          <div className="max-w-[75ch]">
            <p>{s.decision}</p>
            {s.warnings?.map((w) => (
              <p key={w} className="mt-1 text-sm font-medium text-warn">
                Warning: {w}
              </p>
            ))}
          </div>
          <div className="space-y-1 text-sm">
            {s.policyCitation &&
              (onOpenPage ? (
                <button
                  type="button"
                  onClick={() => onOpenPage(citedPage(s.policyCitation ?? ""))}
                  className="block min-h-6 text-left underline decoration-guard/40 underline-offset-2 hover:decoration-guard"
                >
                  <Cite text={s.policyCitation} />
                  <span className="sr-only">: open the PDF at this page</span>
                </button>
              ) : (
                <p>
                  <Cite text={s.policyCitation} />
                </p>
              ))}
            {s.gridCitation && (
              <p>
                <Cite text={s.gridCitation} />
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
