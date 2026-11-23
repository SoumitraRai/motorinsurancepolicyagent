import { useEffect, useState } from "react";
import type { Status } from "../api";

// Timings measured on 2 vCPUs (2026-11-23): RapidOCR ≈ 15 s per page read; Tesseract ≈ 10 s per page,
// but only on the few pages the facts came from (folded into the overhead). The server reports no
// progress, so the bar shows elapsed time against this estimate and never reaches 100% on its own.
// Recalibrate from `meta.seconds` of hosted runs.
const READ_PAGES = 20; // the worker reads only the first 20 pages (READ_PAGES)
const OVERHEAD_S = 30;
const PER_PAGE_S = 16;
const MAX_SHOWN = 95;

export function estimateSeconds(pageCount: number): number {
  return OVERHEAD_S + PER_PAGE_S * Math.min(Math.max(pageCount, 1), READ_PAGES);
}

function duration(s: number): string {
  const m = Math.floor(s / 60);
  const rest = Math.round(s % 60);
  if (m === 0) return `${rest} s`;
  return rest ? `${m} min ${rest} s` : `${m} min`;
}

/** Elapsed-time progress for a queued or processing run, with an estimate of the time left. */
export function AnalysisProgress({
  createdAt,
  pageCount,
  status,
  now,
}: {
  createdAt: string;
  pageCount: number;
  status: Status;
  now?: Date; // fixed clock for tests; otherwise the bar ticks every second
}) {
  const [tick, setTick] = useState(() => new Date());
  useEffect(() => {
    if (now) return;
    const id = window.setInterval(() => setTick(new Date()), 1000);
    return () => window.clearInterval(id);
  }, [now]);

  const elapsed = Math.max(
    0,
    ((now ?? tick).getTime() - Date.parse(createdAt)) / 1000,
  );
  const total = estimateSeconds(pageCount);
  const percent = Math.min(MAX_SHOWN, Math.round((elapsed / total) * 100));
  const left = total - elapsed;
  const pages = Math.min(pageCount, READ_PAGES);

  return (
    <div className="max-w-[75ch] space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="font-medium text-ink">
          {status === "queued"
            ? "Waiting for the analysis worker…"
            : `Reading ${pages} ${pages === 1 ? "page" : "pages"}, extracting facts, resolving the grid`}
        </p>
        <p className="text-sm text-ink-muted tabular-nums">
          {left > 0
            ? `About ${duration(left)} left`
            : "Taking longer than estimated; still working"}
        </p>
      </div>
      <div
        role="progressbar"
        aria-label="Analysis progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-valuetext={`${percent}%, estimated`}
        className="h-2 overflow-hidden rounded-sm bg-guard-tint"
      >
        <div
          className="h-full bg-guard transition-[width] duration-1000 ease-linear motion-reduce:transition-none"
          style={{ width: `${percent}%` }}
        />
      </div>
      <p className="text-sm text-ink-muted">
        Estimated from the page count. This page updates by itself; you can
        leave and come back.
      </p>
    </div>
  );
}
