import { render, screen } from "@testing-library/react";
import { AnalysisProgress, estimateSeconds } from "./AnalysisProgress";

const start = "2026-11-23T10:00:00Z";
const at = (s: number) => new Date(Date.parse(start) + s * 1000);

test("estimate grows with the pages read, up to the 20-page read limit", () => {
  expect(estimateSeconds(9)).toBeGreaterThan(estimateSeconds(4));
  expect(estimateSeconds(200)).toBe(estimateSeconds(20));
});

test("shows elapsed progress and the time left", () => {
  const total = estimateSeconds(4);
  render(
    <AnalysisProgress
      createdAt={start}
      pageCount={4}
      status="processing"
      now={at(total / 2)}
    />,
  );
  const bar = screen.getByRole("progressbar", { name: "Analysis progress" });
  expect(bar).toHaveAttribute("aria-valuenow", "50");
  expect(screen.getByText(/left/)).toBeInTheDocument();
  expect(screen.getByText(/4 pages/)).toBeInTheDocument();
});

test("never shows 100% before the run finishes, and says when it runs long", () => {
  render(
    <AnalysisProgress
      createdAt={start}
      pageCount={4}
      status="processing"
      now={at(10_000)}
    />,
  );
  expect(screen.getByRole("progressbar")).toHaveAttribute(
    "aria-valuenow",
    "95",
  );
  expect(screen.getByText(/longer than estimated/)).toBeInTheDocument();
});

test("a queued run says it is waiting for the worker", () => {
  render(
    <AnalysisProgress
      createdAt={start}
      pageCount={4}
      status="queued"
      now={at(5)}
    />,
  );
  expect(
    screen.getByText(/Waiting for the analysis worker/),
  ).toBeInTheDocument();
});
