# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Vaatun's hiring-team reviewers, evaluating the INS/001 submission. They work at a desktop in focused review
sessions: they upload motor policy PDFs (mostly private cars from Go Digit, HDFC ERGO, Reliance and Tata
AIG), compare each result against the source PDF and the insurer's grid, and ask the author to trace
specific results back to the code. One shared reviewer login.

## Product Purpose

Upload a motor insurance policy PDF and get the broker's OD and TP commission rates, resolved
deterministically from the insurer's supplied grid, with an exact citation for every number. Each run
ends `resolved`, `unsupported` or `ambiguous`, and runs persist across refresh, sign-out and redeploy.
Success: a reviewer can confirm any result is right, or see exactly why the agent refused, without
asking.

## Positioning

The LLM only reads the policy; the rate comes from deterministic, tested code that cites the PDF page and
the grid file, sheet and cell (or PDF table row). The agent never infers through a missing, declined,
contradictory or out-of-scope rule: it refuses with the reason instead of guessing.

## Operating Context

- A run is: upload → OCR (local, scanned PDFs) → fact extraction with quotes → quote verification →
  grid selection, date check, mapping, row match, exceptions → result.
- Reviewers cross-check against the original PDF (opened from the run) and the grid files in the
  challenge bundle.
- Results follow the challenge's example JSON keys; the JSON is viewable and downloadable.
- When a fact is missing and would change the rate, the reviewer can supply it and re-run (a linked
  child run).

## Capabilities and Constraints

- Screens: sign-in, history (all runs, newest first), upload, run detail (rates, confidence, trace,
  facts, JSON, clarification).
- Statuses: queued, processing, resolved, unsupported, ambiguous, failed.
- Stand-alone TP: OD shows "not applicable", never 0%. Package grids may publish no TP rate: "applicable,
  not published", with the grid cell cited.
- Confidence: high, medium or low, with the weakest-link reason and any caps.
- Citations must render exactly, including significant spaces in sheet names (`'4W  RTO'`).
- Stack: React 18, Vite, TypeScript, Tailwind, TanStack Query, supabase-js; hash routes; served by FastAPI.

## Brand Commitments

Name: **Brokerage Rate Agent**. Own identity: no Vaatun or insurer branding; insurer names appear only as
data.

## Evidence on Hand

The four sample results in `samples/output/*.json` and their readable traces (`*.md`). No testimonials,
metrics or customers exist; none may be invented.

## Product Principles

1. The answer and its proof come first: rate, status and confidence, each number one step from its
   citation.
2. The reasoning is visible: the trace explains how the engine decided, step by step, in plain words.
3. A refusal is a result, not an error: `unsupported` and `ambiguous` say why, and what would fix it.
4. Never decorate the data: exact values, exact citations, no rounding or paraphrase of what the grid
   says.

## Accessibility & Inclusion

WCAG 2.2 AA: keyboard operable throughout, visible focus, 4.5:1 text contrast, status never by colour
alone, reduced motion respected.
