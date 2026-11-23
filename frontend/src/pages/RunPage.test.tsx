import { screen, waitFor, within } from "@testing-library/react";
import { renderWithApi } from "../testing";
import userEvent from "@testing-library/user-event";
import type { Result, RunDetail } from "../api";
import { RunPage } from "./RunPage";

/** Matches a rendered citation by its exact, byte-for-byte text (pieces render in separate spans). */
const cite = (text: string) => (_: string, el: Element | null) =>
  Boolean(el?.classList.contains("cite") && el.textContent === text);

const base: Omit<RunDetail, "status" | "result"> = {
  id: "r1",
  fileName: "policy.pdf",
  createdAt: "2026-11-21T10:00:00Z",
  pageCount: 4,
  error: null,
  parentRunId: null,
  overrides: null,
};

const satpResult: Result = {
  status: "resolved",
  facts: {
    rto: {
      value: "UP78",
      raw: "UP-78",
      page: 1,
      quote: "RTO Location Kanpur",
      verification: "verified_both",
      confidence: "medium",
      policyCitation: "policy.pdf · page 1",
    },
    manufactureYear: {
      value: null,
      raw: null,
      page: null,
      quote: null,
      verification: "not_found",
      confidence: "unknown",
      policyCitation: null,
    },
  },
  rates: {
    od: {
      applicable: false,
      ratePercent: null,
      reason: "Stand-alone TP policy: OD not applicable",
    },
    tp: {
      applicable: true,
      ratePercent: 20,
      reason: "",
      gridCitation: "g.xlsx · '4W SATP'!E5",
    },
  },
  trace: [
    {
      step: 1,
      kind: "map",
      decision: "RTO maps to cluster X",
      policyCitation: "policy.pdf · page 1",
      gridCitation: "g.xlsx · '4W  RTO'!B9:F9",
      warnings: [],
    },
  ],
  confidence: { level: "medium", reason: "weakest link: OCR-read RTO" },
  notApplied: [],
};

test("processing state polls until the run finishes", async () => {
  const getRun = vi
    .fn()
    .mockResolvedValueOnce({
      ...base,
      status: "processing",
      result: null,
    } satisfies RunDetail)
    .mockResolvedValue({
      ...base,
      status: "resolved",
      result: satpResult,
    } satisfies RunDetail);
  renderWithApi(<RunPage runId="r1" pollMs={10} />, { getRun });
  expect(
    await screen.findByRole("progressbar", { name: "Analysis progress" }),
  ).toBeInTheDocument();
  await waitFor(() =>
    expect(getRun.mock.calls.length).toBeGreaterThanOrEqual(2),
  );
  const tp = await screen.findByRole("region", { name: "TP rate" });
  expect(within(tp).getByText("20%")).toBeInTheDocument();
});

test("done state shows rates, trace with exact citations, facts and confidence", async () => {
  renderWithApi(<RunPage runId="r1" pollMs={10} />, {
    getRun: vi.fn(async (): Promise<RunDetail> => ({
      ...base,
      status: "resolved",
      result: satpResult,
    })),
  });
  const od = await screen.findByRole("region", { name: "OD rate" });
  expect(within(od).getByText("Not applicable")).toBeInTheDocument();
  expect(
    within(od).getByText("Stand-alone TP policy: OD not applicable"),
  ).toBeInTheDocument();
  // Each rate sits directly above its grid citation.
  const tp = screen.getByRole("region", { name: "TP rate" });
  expect(
    within(tp).getByText(cite("g.xlsx · '4W SATP'!E5")),
  ).toBeInTheDocument();
  // The run serial is printed on the schedule band.
  expect(screen.getByText("Run R1")).toBeInTheDocument();
  // Sheet names are cited byte-for-byte: the double space in '4W  RTO' must survive.
  expect(
    screen.getByText(cite("g.xlsx · '4W  RTO'!B9:F9")),
  ).toBeInTheDocument();
  expect(screen.getByText("RTO maps to cluster X")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("tab", { name: "Schedule fields" }));
  expect(screen.getByText("Not found")).toBeInTheDocument();
  expect(screen.getByText(/weakest link: OCR-read RTO/)).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Resolved");
});

test("failed state offers a retry", async () => {
  const retryRun = vi.fn(async () => ({ id: "r1" }));
  renderWithApi(<RunPage runId="r1" pollMs={10} />, {
    getRun: vi.fn(async (): Promise<RunDetail> => ({
      ...base,
      status: "failed",
      error: "Analysis failed. Retry this run.",
      result: null,
    })),
    retryRun,
  });
  const button = await screen.findByRole("button", { name: "Retry this run" });
  button.click();
  await waitFor(() => expect(retryRun).toHaveBeenCalledWith("r1"));
});

test("tabs follow the ARIA tabs pattern: arrow keys move, panel is labelled", async () => {
  renderWithApi(<RunPage runId="r1" pollMs={10} />, {
    getRun: vi.fn(async (): Promise<RunDetail> => ({
      ...base,
      status: "resolved",
      result: satpResult,
    })),
  });
  const trace = await screen.findByRole("tab", { name: "Decision trace" });
  expect(trace).toHaveAttribute("aria-selected", "true");
  expect(trace).toHaveAttribute("tabindex", "0");
  const fields = screen.getByRole("tab", { name: "Schedule fields" });
  expect(fields).toHaveAttribute("tabindex", "-1");
  trace.focus();
  await userEvent.keyboard("{ArrowRight}");
  expect(fields).toHaveFocus();
  expect(fields).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel")).toHaveAccessibleName("Schedule fields");
  await userEvent.keyboard("{End}");
  expect(screen.getByRole("tab", { name: "JSON" })).toHaveFocus();
  await userEvent.keyboard("{Home}");
  expect(trace).toHaveFocus();
});

test("a refusal says why inside the schedule", async () => {
  renderWithApi(<RunPage runId="r1" pollMs={10} />, {
    getRun: vi.fn(async (): Promise<RunDetail> => ({
      ...base,
      status: "unsupported",
      result: {
        ...satpResult,
        status: "unsupported",
        rates: {
          od: {
            applicable: false,
            ratePercent: null,
            reason: "Stand-alone TP policy: OD not applicable",
          },
          tp: {
            applicable: true,
            ratePercent: null,
            reason: "No row matches this policy.",
          },
        },
      },
    })),
  });
  const why = await screen.findByRole("region", {
    name: "Why there is no rate",
  });
  expect(
    within(why).getByText("No row matches this policy."),
  ).toBeInTheDocument();
});

test("a processing run shows a progress bar with the time left", async () => {
  const getRun = vi.fn().mockResolvedValue({
    ...base,
    createdAt: new Date().toISOString(),
    status: "processing",
    result: null,
  } satisfies RunDetail);
  renderWithApi(<RunPage runId="r1" pollMs={60_000} />, { getRun });
  expect(
    await screen.findByRole("progressbar", { name: "Analysis progress" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/left/)).toBeInTheDocument();
});
