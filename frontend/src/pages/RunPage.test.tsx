import { getDefaultNormalizer, screen, waitFor } from "@testing-library/react";
import { renderWithApi } from "../testing";
import userEvent from "@testing-library/user-event";
import type { Result, RunDetail } from "../api";
import { RunPage } from "./RunPage";

const base: Omit<RunDetail, "status" | "result"> = {
  id: "r1", fileName: "policy.pdf", createdAt: "2026-11-21T10:00:00Z", pageCount: 4,
  error: null, parentRunId: null, overrides: null,
};

const satpResult: Result = {
  status: "resolved",
  facts: {
    rto: { value: "UP78", raw: "UP-78", page: 1, quote: "RTO Location Kanpur", verification: "verified_both", confidence: "medium", policyCitation: "policy.pdf · page 1" },
    manufactureYear: { value: null, raw: null, page: null, quote: null, verification: "not_found", confidence: "unknown", policyCitation: null },
  },
  rates: {
    od: { applicable: false, ratePercent: null, reason: "Stand-alone TP policy: OD not applicable" },
    tp: { applicable: true, ratePercent: 20, reason: "", gridCitation: "g.xlsx · '4W SATP'!E5" },
  },
  trace: [
    { step: 1, kind: "map", decision: "RTO maps to cluster X", policyCitation: "policy.pdf · page 1", gridCitation: "g.xlsx · '4W  RTO'!B9:F9", warnings: [] },
  ],
  confidence: { level: "medium", reason: "weakest link: OCR-read RTO" },
  notApplied: [],
};

test("processing state polls until the run finishes", async () => {
  const getRun = vi
    .fn()
    .mockResolvedValueOnce({ ...base, status: "processing", result: null } satisfies RunDetail)
    .mockResolvedValue({ ...base, status: "resolved", result: satpResult } satisfies RunDetail);
  renderWithApi(<RunPage runId="r1" pollMs={10} />, { getRun });
  expect(await screen.findByText(/Analysing this policy/)).toBeInTheDocument();
  await waitFor(() => expect(getRun.mock.calls.length).toBeGreaterThanOrEqual(2));
  expect(await screen.findByText("TP 20%")).toBeInTheDocument();
});

test("done state shows rates, trace with exact citations, facts and confidence", async () => {
  renderWithApi(<RunPage runId="r1" pollMs={10} />, {
    getRun: vi.fn(async (): Promise<RunDetail> => ({ ...base, status: "resolved", result: satpResult })),
  });
  expect(await screen.findByText("OD Not applicable")).toBeInTheDocument();
  expect(screen.getByText("Stand-alone TP policy: OD not applicable")).toBeInTheDocument();
  // Sheet names are cited byte-for-byte, so compare without collapsing the double space.
  const exact = { normalizer: getDefaultNormalizer({ collapseWhitespace: false, trim: false }) };
  expect(screen.getByText("g.xlsx · '4W  RTO'!B9:F9", exact)).toBeInTheDocument();
  expect(screen.getByText("RTO maps to cluster X")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Facts" }));
  expect(screen.getByText("Not found")).toBeInTheDocument();
  expect(screen.getByText(/weakest link: OCR-read RTO/)).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Resolved");
});

test("failed state offers a retry", async () => {
  const retryRun = vi.fn(async () => ({ id: "r1" }));
  renderWithApi(<RunPage runId="r1" pollMs={10} />, {
    getRun: vi.fn(
      async (): Promise<RunDetail> => ({ ...base, status: "failed", error: "Analysis failed. Retry this run.", result: null }),
    ),
    retryRun,
  });
  const button = await screen.findByRole("button", { name: "Retry this run" });
  button.click();
  await waitFor(() => expect(retryRun).toHaveBeenCalledWith("r1"));
});
