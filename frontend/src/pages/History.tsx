import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiError, useApi } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import { UploadDrop } from "../components/UploadDrop";
import { rateText } from "../components/rates";

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

export function History() {
  const api = useApi();
  const qc = useQueryClient();
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns(),
    refetchInterval: 5000,
  });
  const upload = useMutation({
    mutationFn: (file: File) => api.uploadRun(file),
    onSuccess: ({ id }) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      window.location.hash = `#/runs/${id}`;
    },
  });
  const showSkeleton = useDelayed(runs.isPending);
  const items = runs.data?.items ?? [];

  return (
    <div className="space-y-6">
      <UploadDrop
        onUpload={(f) => upload.mutate(f)}
        busy={upload.isPending}
        serverError={
          upload.error instanceof ApiError
            ? upload.error.message
            : upload.error
              ? "Upload failed. Try again."
              : null
        }
      />
      <section aria-labelledby="history-h">
        <h2 id="history-h" className="mb-2 text-lg font-semibold">
          History
        </h2>
        {runs.isError && (
          <p role="alert">
            Couldn't load your runs. Refresh the page to try again.
          </p>
        )}
        {runs.isPending && showSkeleton && (
          <div aria-hidden="true" className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-8 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        )}
        {runs.isSuccess && items.length === 0 && (
          <p className="text-slate-700">
            No policies yet. Upload a motor policy PDF to get its brokerage
            rate.
          </p>
        )}
        {items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 pr-3">File</th>
                  <th className="py-2 pr-3">Uploaded</th>
                  <th className="py-2 pr-3">Insurer</th>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">OD</th>
                  <th className="py-2">TP</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-b">
                    <td className="py-2 pr-3">
                      <a
                        className="text-sky-800 underline"
                        href={`#/runs/${r.id}`}
                      >
                        {r.fileName}
                      </a>
                    </td>
                    <td className="py-2 pr-3">
                      {new Date(r.createdAt).toLocaleString()}
                    </td>
                    <td className="py-2 pr-3">{r.insurer ?? "—"}</td>
                    <td className="py-2 pr-3">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="py-2 pr-3">{rateText(r.od)}</td>
                    <td className="py-2">{rateText(r.tp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
