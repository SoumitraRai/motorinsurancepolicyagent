import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useApi, type RunDetail } from "../api";
import { ClarifyPanel } from "../components/ClarifyPanel";
import { FactsTable } from "../components/FactsTable";
import { RatesCard } from "../components/RatesCard";
import { StatusBadge, statusLabel } from "../components/StatusBadge";
import { TraceList } from "../components/TraceList";

const PENDING = new Set(["queued", "processing"]);
type Tab = "trace" | "facts" | "json";

export function RunPage({
  runId,
  pollMs = 3000,
}: {
  runId: string;
  pollMs?: number;
}) {
  const api = useApi();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("trace");
  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (q) =>
      q.state.data && PENDING.has(q.state.data.status) ? pollMs : false,
  });
  const retry = useMutation({
    mutationFn: () => api.retryRun(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["run", runId] }),
  });
  const clarify = useMutation({
    mutationFn: (facts: Record<string, string>) => api.clarifyRun(runId, facts),
    onSuccess: ({ id }) => {
      window.location.hash = `#/runs/${id}`;
    },
  });

  async function openPdf() {
    const url = await api.pdfUrl(runId);
    window.open(url, "_blank", "noopener");
  }

  if (run.isError)
    return (
      <p role="alert">
        Couldn't load this run. Go back to History and try again.
      </p>
    );
  if (!run.data) return <p className="text-slate-600">Loading…</p>;
  const r: RunDetail = run.data;
  const res = r.result;

  return (
    <div className="space-y-6">
      <p>
        <a href="#/" className="text-sky-800 underline">
          ← History
        </a>
      </p>
      <header className="space-y-2">
        <h2 className="text-xl font-semibold">{r.fileName}</h2>
        <div className="flex items-center gap-3">
          <StatusBadge status={r.status} />
          <p role="status" aria-live="polite" className="sr-only">
            {statusLabel(r.status)}
          </p>
          <button
            type="button"
            onClick={openPdf}
            className="text-sm text-sky-800 underline"
          >
            Open the PDF
          </button>
          {r.parentRunId && (
            <a
              href={`#/runs/${r.parentRunId}`}
              className="text-sm text-sky-800 underline"
            >
              Original run (this one uses reviewer-supplied facts)
            </a>
          )}
        </div>
      </header>

      {PENDING.has(r.status) && (
        <p className="rounded border border-sky-200 bg-sky-50 p-4">
          Analysing this policy: reading pages, extracting facts, checking
          quotes, resolving the grid. This page updates by itself; you can leave
          and come back.
        </p>
      )}

      {r.status === "failed" && (
        <div className="space-y-2 rounded border border-rose-300 bg-rose-50 p-4">
          <p>{r.error ?? "Analysis failed."}</p>
          <button
            type="button"
            onClick={() => retry.mutate()}
            disabled={retry.isPending}
            className="min-h-11 rounded bg-rose-800 px-4 font-medium text-white disabled:opacity-60"
          >
            Retry this run
          </button>
        </div>
      )}

      {res && (
        <>
          <RatesCard od={res.rates.od} tp={res.rates.tp} />
          <section
            aria-labelledby="conf-h"
            className="rounded border border-slate-200 p-4"
          >
            <h2 id="conf-h" className="font-semibold">
              Confidence: {res.confidence.level}
            </h2>
            <p className="text-sm text-slate-700">{res.confidence.reason}</p>
            <p className="mt-1 text-xs text-slate-600">
              Facts read by OCR from scanned pages are capped at medium, even
              when both OCR engines agree.
            </p>
          </section>
          {res.notApplied && res.notApplied.length > 0 && (
            <section className="rounded border border-amber-300 bg-amber-50 p-4 text-sm">
              <h2 className="font-semibold">Possible, not applied</h2>
              <ul className="list-disc pl-5">
                {res.notApplied.map((n) => (
                  <li key={n.rule}>
                    {n.rule}: {n.why}
                    {n.gridCitation && (
                      <span className="ml-1 font-mono text-xs">
                        ({n.gridCitation})
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
          {r.status === "ambiguous" && res.clarification?.facts?.length ? (
            <ClarifyPanel
              facts={res.clarification.facts}
              onSubmit={(v) => clarify.mutate(v)}
              busy={clarify.isPending}
            />
          ) : null}
          <div
            role="tablist"
            aria-label="Run details"
            className="flex gap-2 border-b"
          >
            {(["trace", "facts", "json"] as Tab[]).map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={`min-h-11 px-3 ${tab === t ? "border-b-2 border-sky-700 font-semibold" : ""}`}
              >
                {{ trace: "Decision trace", facts: "Facts", json: "JSON" }[t]}
              </button>
            ))}
          </div>
          <div role="tabpanel">
            {tab === "trace" && (
              <TraceList steps={res.trace} onOpenPage={openPdf} />
            )}
            {tab === "facts" && <FactsTable facts={res.facts} />}
            {tab === "json" && (
              <div className="space-y-2">
                <a
                  className="text-sm text-sky-800 underline"
                  download={`${r.fileName}.result.json`}
                  href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(res, null, 2))}`}
                >
                  Download JSON
                </a>
                <pre className="overflow-x-auto rounded bg-slate-50 p-3 text-xs">
                  {JSON.stringify(res, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
