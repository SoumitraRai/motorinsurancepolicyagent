import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useApi, type RunSummary } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import { UploadDrop } from "../components/UploadDrop";
import { rateText } from "../components/rates";
import { useUpload } from "../upload";

/** True once `flag` has stayed true for `ms` (skeletons only appear on slow loads, ux-standards). */
function useDelayed(flag: boolean, ms = 300): boolean {
  const [elapsed, setElapsed] = useState(false);
  useEffect(() => {
    if (!flag) return;
    const t = setTimeout(() => setElapsed(true), ms);
    return () => clearTimeout(t);
  }, [flag, ms]);
  return flag && elapsed;
}

const when = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

function Row({ r, current }: { r: RunSummary; current: boolean }) {
  return (
    <tr
      className={`group relative border-b border-rule align-top transition-colors duration-150 focus-within:outline focus-within:outline-2 focus-within:-outline-offset-2 focus-within:outline-guard ${current ? "bg-guard-tint" : "hover:bg-sheet-wash"}`}
    >
      <td className="py-3 pl-4 pr-2">
        <a
          href={`#/runs/${r.id}`}
          aria-current={current ? "page" : undefined}
          className="font-semibold text-ink [overflow-wrap:anywhere] after:absolute after:inset-0 focus-visible:outline-none group-focus-within:underline"
        >
          {r.fileName}
        </a>
        <p
          className="mt-0.5 truncate text-[0.8125rem] text-ink-muted"
          title={r.insurer ?? undefined}
        >
          {r.insurer ?? "Insurer not read"}
        </p>
        <p className="flex flex-wrap gap-x-3 text-[0.8125rem] text-ink-muted">
          <span>
            OD{" "}
            <span className="tabular text-ink">
              {rateText(r.od, r.status === "resolved")}
            </span>
          </span>
          <span>
            TP{" "}
            <span className="tabular text-ink">
              {rateText(r.tp, r.status === "resolved")}
            </span>
          </span>
        </p>
        <p className="text-[0.8125rem] text-ink-muted">
          {when.format(new Date(r.createdAt))}
        </p>
      </td>
      <td className="py-3 pr-4 text-right">
        <StatusBadge status={r.status} />
      </td>
    </tr>
  );
}

/** The run list: every upload, newest first, with its verdict and rates at a glance. */
export function History({
  currentId = null,
  showUpload = true,
}: {
  currentId?: string | null;
  showUpload?: boolean;
}) {
  const api = useApi();
  const upload = useUpload();
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(),
    refetchInterval: 5000,
  });
  const showSkeleton = useDelayed(runs.isPending);
  const items = runs.data?.items ?? [];

  return (
    <div className="flex flex-col gap-5">
      {showUpload && (
        <UploadDrop
          onUpload={upload.start}
          busy={upload.busy}
          serverError={upload.serverError}
        />
      )}
      <section aria-labelledby="history-h">
        <h2 id="history-h" className="mb-2 text-lg font-semibold">
          History
        </h2>
        {runs.isError && (
          <p role="alert" className="text-refuse">
            Couldn't load your runs. Refresh the page to try again.
          </p>
        )}
        {runs.isPending && showSkeleton && (
          <div aria-hidden="true" className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded bg-rule/60" />
            ))}
          </div>
        )}
        {runs.isSuccess && items.length === 0 && (
          <p className="text-ink-muted">
            No policies yet for this account. Runs are private to each login.
            Upload a motor policy PDF to get its brokerage rate.
          </p>
        )}
        {items.length > 0 && (
          <table className="w-full table-fixed border-t border-rule text-left">
            <colgroup>
              <col />
              <col className="w-[7.5rem]" />
            </colgroup>
            <thead className="sr-only">
              <tr>
                <th scope="col">Policy</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <Row key={r.id} r={r} current={r.id === currentId} />
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
