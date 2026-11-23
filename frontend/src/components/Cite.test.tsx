import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Cite, citedPage } from "./Cite";
import { TraceList } from "./TraceList";

test("a sheet name's double space is kept and never broken across lines", () => {
  const { container } = render(
    <Cite text="raters/godigit/x.xlsx · '4W  RTO'!B1609:C1609" />,
  );
  expect(container.textContent).toBe(
    "raters/godigit/x.xlsx · '4W  RTO'!B1609:C1609",
  );
  const kept = [...container.querySelectorAll(".whitespace-pre")].map(
    (s) => s.textContent,
  );
  expect(kept).toEqual(["'4W  RTO'!B1609:C1609"]);
});

test("a long path with a double space still wraps everywhere else", () => {
  const text =
    "raters/reliance-indusind/feb-2026/Reliance Broking Premier  FEB 26 Grid.xlsx · 'PRIVATE CAR COMP, SAOD & STP'!A1";
  const { container } = render(<Cite text={text} />);
  expect(container.textContent).toBe(text);
  const kept = [...container.querySelectorAll(".whitespace-pre")].map(
    (s) => s.textContent,
  );
  expect(kept).toEqual(["Premier  FEB"]); // only the double-space run is held together
});

test("a policy citation opens the PDF at its page", async () => {
  expect(citedPage("policy.pdf · page 7")).toBe(7);
  const open = vi.fn();
  render(
    <TraceList
      onOpenPage={open}
      steps={[
        {
          step: 1,
          kind: "map",
          decision: "x",
          policyCitation: "policy.pdf · page 3",
        },
      ]}
    />,
  );
  await userEvent.click(
    screen.getByRole("button", { name: /open the PDF at this page/ }),
  );
  expect(open).toHaveBeenCalledWith(3);
});

test("the confidence reason is written in the reviewer's words, with the fact's quote", async () => {
  const { confidenceText } = await import("./RatesCard");
  const c = confidenceText("weakest link: cc (verified one, page 1)", {
    cc: {
      value: 1086,
      page: 1,
      quote: "Cubic Capacity 1086CC",
      verification: "verified_one",
      confidence: "low",
    },
  });
  expect(c.text).toBe(
    "Weakest link: Engine CC, read by one OCR engine (page 1)",
  );
  expect(c.quote).toBe("Cubic Capacity 1086CC");
});

test("the confirmed share leads the confidence text; a weak rate-row fact is named", async () => {
  const { confidenceText } = await import("./RatesCard");
  const cc = {
    value: 1086,
    page: 1,
    quote: "Cubic Capacity 1086CC",
    verification: "verified_one" as const,
    confidence: "low" as const,
  };
  expect(
    confidenceText("10 of 10 facts the result used confirmed (100%)", {}).text,
  ).toBe("10 of 10 facts confirmed by both OCR engines (100%)");
  const row = confidenceText(
    "9 of 10 facts the result used confirmed (90%); a fact that picked the rate row is weak: cc (verified one, page 1)",
    { cc },
  );
  expect(row.text).toBe(
    "9 of 10 facts confirmed by both OCR engines (90%). A fact that picked the rate row is weak: Engine CC, read by one OCR engine (page 1)",
  );
  expect(row.quote).toBe("Cubic Capacity 1086CC");
  const capped = confidenceText(
    "9 of 10 facts the result used confirmed (90%); weakest link: cc (verified one, page 1); capped by slab (C1)",
    { cc },
  );
  expect(capped.text).toBe(
    "9 of 10 facts confirmed by both OCR engines (90%). Weakest link: Engine CC, read by one OCR engine (page 1); capped by slab (C1)",
  );
});
