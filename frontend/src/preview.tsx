// Local preview only (npm run preview:local): the real screens with a fake sign-in and the committed
// sample results from samples/output/. Not part of the built app; no backend or Supabase needed.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import type { Api, Result, RunDetail, RunSummary } from "./api";
import type { Auth } from "./auth";
import "./index.css";

const files = import.meta.glob<Result>("../../samples/output/*.json", {
  eager: true,
  import: "default",
});

const runs: RunDetail[] = Object.entries(files).map(([path, result], i) => ({
  id:
    ["7f3a91c2", "b04e6d18", "c91d27a5", "e5a8304f"][i % 4] +
    "-4c1e-9b2a-sample",
  fileName: path
    .split("/")
    .pop()!
    .replace(/\.json$/, ".pdf"),
  createdAt: new Date(Date.UTC(2026, 10, 22, 9, i)).toISOString(),
  status: result.status,
  pageCount: Number(result.meta?.pageCount ?? 0),
  error: null,
  parentRunId: null,
  overrides: null,
  result,
}));

function summary(r: RunDetail): RunSummary {
  const insurer = r.result?.facts.insurer?.value;
  return {
    id: r.id,
    fileName: r.fileName,
    createdAt: r.createdAt,
    status: r.status,
    insurer: insurer == null ? null : String(insurer),
    od: r.result?.rates.od ?? null,
    tp: r.result?.rates.tp ?? null,
  };
}

let nextId = 1;
const api: Api = {
  async listRuns() {
    const items = [...runs]
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .map(summary);
    return { items, nextCursor: null };
  },
  async getRun(id) {
    const run = runs.find((r) => r.id === id);
    if (!run) throw new Error("not found");
    return run;
  },
  async uploadRun(file) {
    const id = `upload-${nextId++}`;
    const run: RunDetail = {
      id,
      fileName: file.name,
      createdAt: new Date().toISOString(),
      status: "processing",
      pageCount: 0,
      error: null,
      parentRunId: null,
      overrides: null,
      result: null,
    };
    runs.push(run);
    setTimeout(() => {
      run.status = "failed";
      run.error =
        "Preview mode: there is no backend, so the PDF was not analysed.";
    }, 4000);
    return { id };
  },
  async retryRun(id) {
    return { id };
  },
  async clarifyRun(id) {
    return { id };
  },
  async pdfUrl() {
    return "about:blank";
  },
};

// `?as=<email>` starts signed in, so headless screenshots can reach the signed-in screens.
let email: string | null = new URLSearchParams(window.location.search).get(
  "as",
);
const listeners = new Set<() => void>();
const auth: Auth = {
  token: async () => (email ? "preview-token" : null),
  email: () => email,
  async signIn(e) {
    email = e;
    listeners.forEach((cb) => cb());
  },
  async signOut() {
    email = null;
    listeners.forEach((cb) => cb());
  },
  subscribe(cb) {
    listeners.add(cb);
    cb();
    return () => listeners.delete(cb);
  },
};

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App auth={auth} api={api} />
  </StrictMode>,
);
