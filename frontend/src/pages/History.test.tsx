import { screen } from "@testing-library/react";
import { renderWithApi } from "../testing";
import type { RunSummary } from "../api";
import { History } from "./History";

test("shows the empty state copy when there are no runs", async () => {
  renderWithApi(<History />, {});
  expect(
    await screen.findByText("No policies yet. Upload a motor policy PDF to get its brokerage rate."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Upload a policy PDF" })).toBeInTheDocument();
});

test("renders one row per run with status as text", async () => {
  renderWithApi(<History />, {
    listRuns: vi.fn(async () => ({
      nextCursor: null,
      items: ([
        { id: "r1", fileName: "a.pdf", createdAt: "2026-11-21T10:00:00Z", status: "ambiguous", insurer: "Go Digit", od: { applicable: false, ratePercent: null }, tp: { applicable: true, ratePercent: 12.5 } },
        { id: "r2", fileName: "b.pdf", createdAt: "2026-11-21T09:00:00Z", status: "processing", insurer: null, od: null, tp: null },
      ] satisfies RunSummary[]),
    })),
  });
  const rows = await screen.findAllByRole("row");
  expect(rows).toHaveLength(3); // header + 2
  expect(screen.getByText("a.pdf")).toBeInTheDocument();
  expect(screen.getByText("Ambiguous")).toBeInTheDocument();
  expect(screen.getByText("Processing")).toBeInTheDocument();
  expect(screen.getByText("Not applicable")).toBeInTheDocument();
  expect(screen.getByText("12.5%")).toBeInTheDocument();
});
