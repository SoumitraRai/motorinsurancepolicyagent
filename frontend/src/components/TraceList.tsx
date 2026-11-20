import type { TraceStep } from "../api";

export function TraceList({
  steps,
  onOpenPage,
}: {
  steps: TraceStep[];
  onOpenPage?: () => void;
}) {
  if (steps.length === 0)
    return <p className="text-slate-600">No decision steps were recorded.</p>;
  return (
    <ol className="space-y-3">
      {steps.map((s) => (
        <li key={s.step} className="rounded border border-slate-200 p-3">
          <p className="font-medium">
            <span className="mr-2 text-slate-500">{s.step}.</span>
            {s.decision}
          </p>
          {s.policyCitation && (
            <p className="mt-1 text-sm">
              <span className="text-slate-600">Policy: </span>
              {onOpenPage ? (
                <button
                  type="button"
                  className="font-mono text-sky-800 underline"
                  onClick={onOpenPage}
                >
                  {s.policyCitation}
                </button>
              ) : (
                <span className="font-mono">{s.policyCitation}</span>
              )}
            </p>
          )}
          {s.gridCitation && (
            <p className="mt-1 text-sm">
              <span className="text-slate-600">Grid: </span>
              <span className="whitespace-pre-wrap font-mono">
                {s.gridCitation}
              </span>
            </p>
          )}
          {s.warnings?.map((w) => (
            <p key={w} className="mt-1 text-sm text-amber-900">
              Warning: {w}
            </p>
          ))}
        </li>
      ))}
    </ol>
  );
}
