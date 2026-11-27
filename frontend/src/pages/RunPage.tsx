import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useApi, type RunDetail } from "../api";
import { AnalysisProgress } from "../components/AnalysisProgress";
import { Cite } from "../components/Cite";
import { ClarifyPanel } from "../components/ClarifyPanel";
import { FactsTable } from "../components/FactsTable";
import { RatesCard } from "../components/RatesCard";
import { statusLabel } from "../components/StatusBadge";
import { TraceList } from "../components/TraceList";

const PENDING = new Set(["queued", "processing"]);
const TABS = [
  { id: "trace", label: "Decision trace" },
  { id: "facts", label: "Schedule fields" },
  { id: "json", label: "JSON" },
] as const;
type Tab = (typeof TABS)[number]["id"];

const when = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** True when the run finished while this page watched it: the schedule then prints once. */
function useJustFinished(status: string | undefined): boolean {
  const seenPending = useRef(false);
  const [finished, setFinished] = useState(false);
  useEffect(() => {
    if (!status) return;
    if (PENDING.has(status)) seenPending.current = true;
    else if (seenPending.current) setFinished(true);
  }, [status]);
  return finished;
}

function Tabs({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  function key(e: KeyboardEvent) {
    const i = TABS.findIndex((t) => t.id === tab);
    const next = {
      ArrowRight: (i + 1) % TABS.length,
      ArrowLeft: (i - 1 + TABS.length) % TABS.length,
      Home: 0,
      End: TABS.length - 1,
    }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    onChange(TABS[next].id);
    refs.current[TABS[next].id]?.focus();
  }
  return (
    <div
      role="tablist"
      aria-label="Run details"
      onKeyDown={key}
      className="flex gap-6 overflow-x-auto border-b border-rule"
    >
      {TABS.map((t) => (
        <button
          key={t.id}
          ref={(el) => {
            refs.current[t.id] = el;
          }}
          type="button"
          role="tab"
          id={`tab-${t.id}`}
          aria-selected={tab === t.id}
          aria-controls={`panel-${t.id}`}
          tabIndex={tab === t.id ? 0 : -1}
          onClick={() => onChange(t.id)}
          className={`-mb-px min-h-11 whitespace-nowrap border-b-2 px-1 transition-colors duration-150 ${
            tab === t.id
              ? "border-ink font-semibold text-ink"
              : "border-transparent text-ink-muted hover:text-ink"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

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
  const printed = useJustFinished(run.data?.status);

  async function openPdf(page?: number) {
    const url = await api.pdfUrl(runId);
    window.open(page ? `${url}#page=${page}` : url, "_blank", "noopener");
  }

  if (run.isError)
    return (
      <p role="alert" className="text-refuse">
        Couldn't load this run.{" "}
        <a href="#/" className="font-medium underline">
          Go back to the run list and try again.
        </a>
      </p>
    );
  if (!run.data)
    return (
      <div aria-hidden="true" className="space-y-4">
        <div className="h-8 w-2/3 animate-pulse rounded bg-rule" />
        <div className="h-48 animate-pulse rounded-sm bg-rule/60" />
      </div>
    );
  const r: RunDetail = run.data;
  const res = r.result;

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <a
          href="#/"
          className="mb-2 inline-flex min-h-11 items-center font-medium text-guard-deep underline lg:hidden"
        >
          All runs
        </a>
        <h2 className="text-2xl font-semibold tracking-tight [overflow-wrap:anywhere]">
          {r.fileName}
        </h2>
        <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-ink-muted">
          <span>Uploaded {when.format(new Date(r.createdAt))}</span>
          {r.pageCount > 0 && (
            <span>
              {r.pageCount} {r.pageCount === 1 ? "page" : "pages"}
            </span>
          )}
          <button
            type="button"
            onClick={() => openPdf()}
            className="min-h-11 font-medium text-guard-deep underline decoration-guard/40 hover:decoration-guard"
          >
            Open the PDF
          </button>
          {r.parentRunId && (
            <a
              href={`#/runs/${r.parentRunId}`}
              className="font-medium text-guard-deep underline decoration-guard/40 hover:decoration-guard"
            >
              Original run (this one uses reviewer-supplied facts)
            </a>
          )}
        </p>
        <p role="status" aria-live="polite" className="sr-only">
          {statusLabel(r.status)}
        </p>
      </header>

      <RatesCard run={r} res={res} printed={printed} />

      {PENDING.has(r.status) && (
        <AnalysisProgress
          createdAt={r.createdAt}
          pageCount={r.pageCount}
          status={r.status}
        />
      )}

      {r.status === "failed" && (
        <div
          role="alert"
          className="space-y-3 rounded-sm border border-refuse/40 bg-refuse-tint p-5"
        >
          <p className="font-medium text-refuse">
            {r.error ?? "Analysis failed."}
          </p>
          <button
            type="button"
            onClick={() => retry.mutate()}
            disabled={retry.isPending}
            className="btn-primary"
          >
            {retry.isPending ? "Retrying…" : "Retry this run"}
          </button>
        </div>
      )}

      {res && (
        <>
          {res.notApplied && res.notApplied.length > 0 && (
            <section aria-labelledby="na-h" className="space-y-2">
              <h2 id="na-h" className="text-lg font-semibold">
                Possible, not applied
              </h2>
              <ul className="divide-y divide-rule border-y border-rule">
                {res.notApplied.map((n) => (
                  <li
                    key={n.rule}
                    className="grid gap-x-6 gap-y-1 py-3 md:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]"
                  >
                    <p className="max-w-[75ch]">
                      {n.rule}
                      <span className="block text-sm text-ink-muted">
                        {n.why}
                      </span>
                    </p>
                    {n.gridCitation && (
                      <p>
                        <Cite text={n.gridCitation} />
                      </p>
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
          <div className="space-y-5">
            <Tabs tab={tab} onChange={setTab} />
            <div
              role="tabpanel"
              id={`panel-${tab}`}
              aria-labelledby={`tab-${tab}`}
              tabIndex={0}
            >
              {tab === "trace" && (
                <TraceList steps={res.trace} onOpenPage={openPdf} />
              )}
              {tab === "facts" && <FactsTable facts={res.facts} />}
              {tab === "json" && (
                <div className="space-y-3">
                  <a
                    className="btn-quiet"
                    download={`${r.fileName}.result.json`}
                    href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(res, null, 2))}`}
                  >
                    Download JSON
                  </a>
                  <pre className="max-h-[32rem] overflow-auto rounded-sm border border-rule bg-sheet-wash p-4 font-mono text-[0.8125rem] leading-relaxed">
                    {JSON.stringify(res, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
