import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { ApiContext, type Api } from "./api";

export function renderWithApi(ui: ReactNode, api: Partial<Api>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const full: Api = {
    listRuns: vi.fn(async () => ({ items: [], nextCursor: null })),
    getRun: vi.fn(),
    uploadRun: vi.fn(),
    retryRun: vi.fn(),
    clarifyRun: vi.fn(),
    pdfUrl: vi.fn(),
    ...api,
  } as Api;
  return { api: full, ...render(<QueryClientProvider client={client}><ApiContext.Provider value={full}>{ui}</ApiContext.Provider></QueryClientProvider>) };
}
