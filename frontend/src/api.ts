import { createContext, useContext } from "react";

export type Status =
  "queued" | "processing" | "resolved" | "unsupported" | "ambiguous" | "failed";

export interface Rate {
  applicable: boolean | null;
  ratePercent: number | null;
  reason?: string;
  gridCitation?: string;
}

export interface Fact {
  value: string | number | null;
  raw?: string | null;
  page: number | null;
  quote: string | null;
  verification: string;
  confidence: string;
  policyCitation?: string | null;
}

export interface TraceStep {
  step: number;
  kind: string;
  decision: string;
  policyCitation?: string | null;
  gridCitation?: string | null;
  warnings?: string[];
}

export interface Result {
  status: Status;
  facts: Record<string, Fact>;
  rates: { od?: Rate; tp?: Rate };
  trace: TraceStep[];
  confidence: { level: string; reason: string };
  notApplied?: { rule: string; why: string; gridCitation?: string }[];
  clarification?: { facts: string[] } | null;
  meta?: Record<string, unknown>;
}

export interface RunSummary {
  id: string;
  fileName: string;
  createdAt: string;
  status: Status;
  insurer: string | null;
  od: Rate | null;
  tp: Rate | null;
}

export interface RunDetail {
  id: string;
  fileName: string;
  createdAt: string;
  status: Status;
  pageCount: number;
  error: string | null;
  parentRunId: string | null;
  overrides: Record<string, string> | null;
  result: Result | null;
}

export interface Api {
  listRuns(
    cursor?: string | null,
  ): Promise<{ items: RunSummary[]; nextCursor: string | null }>;
  getRun(id: string): Promise<RunDetail>;
  uploadRun(file: File): Promise<{ id: string }>;
  retryRun(id: string): Promise<{ id: string }>;
  clarifyRun(
    id: string,
    facts: Record<string, string>,
  ): Promise<{ id: string }>;
  pdfUrl(id: string): Promise<string>;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** HTTP client for the backend. `token` returns the current Supabase access token. */
export function httpApi(token: () => Promise<string | null>, base = ""): Api {
  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const t = await token();
    const resp = await fetch(base + path, {
      ...init,
      headers: {
        ...(init.headers ?? {}),
        ...(t ? { Authorization: `Bearer ${t}` } : {}),
      },
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new ApiError(
        resp.status,
        body.detail ?? "Something went wrong. Try again.",
      );
    }
    return resp.json() as Promise<T>;
  }
  return {
    listRuns: (cursor) =>
      call(`/api/runs${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),
    getRun: (id) => call(`/api/runs/${id}`),
    uploadRun: (file) => {
      const form = new FormData();
      form.append("file", file);
      return call("/api/runs", { method: "POST", body: form });
    },
    retryRun: (id) => call(`/api/runs/${id}/retry`, { method: "POST" }),
    clarifyRun: (id, facts) =>
      call(`/api/runs/${id}/clarify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ facts }),
      }),
    pdfUrl: async (id) => {
      const { url } = await call<{ url: string }>(`/api/runs/${id}/pdf`);
      if (!url.startsWith("/api/files/")) return url;
      // Local storage links need the auth header, so fetch and hand back a blob URL.
      const t = await token();
      const resp = await fetch(base + url, {
        headers: t ? { Authorization: `Bearer ${t}` } : {},
      });
      if (!resp.ok)
        throw new ApiError(
          resp.status,
          "This link has expired. Open the PDF again.",
        );
      return URL.createObjectURL(await resp.blob());
    },
  };
}

export const ApiContext = createContext<Api | null>(null);

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error("ApiContext is not provided");
  return api;
}
