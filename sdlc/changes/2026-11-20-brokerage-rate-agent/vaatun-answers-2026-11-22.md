# Vaatun answers, received 2026-11-22

These are the hiring team's written answers to our clarification list. They take precedence over our own
earlier readings (A1–A8, B1–B4, D1–D2, C1–C13), but they come after `challenge.md`. Each "Impact" line says
what would change; the "Applied" section at the end says what was done.

| # | Answer (paraphrased; the quote is in the email) | Current build | Impact |
|---|---|---|---|
| 1 | If a policy's dates fall outside the grid's effective period, **return an error with the reason**. | `GRID_DATE_POLICY` defaults to `warn` (D1): confidence drops one level and the run continues. | Change the default to `strict`, or say why `warn` is still right. This reverses D1. |
| 2 | Most review policies will be **private cars from the four insurers**. Any policy no supplied grid covers (another insurer, a two-wheeler, a commercial vehicle) gets **"unsupported" with the reason**. | A1 full scope: two-wheeler grids are done (T14); CV is in progress (T15, Go Digit CV grid done, uncommitted). Uncovered policies already return `unsupported` with the reason. | Consistent where no grid exists. Two-wheeler and CV work goes beyond what review will mostly test, so private-car accuracy comes first. Whether to finish T15 or narrow A1 is the PO's call. |
| 3 | **The cached value is authoritative.** A formula that disagrees with it can be flagged. | `data_only=True`; a formula with no cached value is `MISSING` (B1). Disagreements are not flagged. | Consistent. Flagging a disagreement is optional and not built. |
| 4 | **Ignore file titles; assume the grids apply.** | `BROKER_ELIGIBILITY=assume_base`. | Consistent. |
| 5 | **Two rows or footnotes that apply with different rates: return a warning or an error, with the reason.** | Returns `ambiguous` and cites both. | Consistent. |
| 6 | **Business type depends on the insurer.** Some grids need the previous insurer (those with separate rollover rates), others don't. **"Ambiguous" only when the missing fact would change the rate.** | Rows: an unknown `business_type` that can't change the rate resolves (`match._irrelevant`). Grid selection: `select.py` returns `ambiguous` whenever any candidate grid splits on business type, even when every candidate would give the same rate. | Possible gap at grid selection. It should check whether the grids that could apply would give the same answer. Needs a failing test first. |
| 7 | Keep the **example JSON's keys and value types**. | Done (`test_example_keys_preserved`). | None. |
| 8 | For stand-alone TP, `"od": {"applicable": false, "ratePercent": null}` is fine. | Done. | None. |
| 9 | Asking questions is fine. Reviewers answer during the review. | — | None. |
| 10 | **Policy PDFs may be sent to the Anthropic API and an OCR service.** | OpenRouter plus local rules; there is no Anthropic key (PO). | Allowed now, but still blocked on a key. The README privacy note can cite this permission. |
| 11 | PDFs may be large; **the important details are in the first 5–6 pages**. | Upload limit is 60 pages; every page is OCR'd one at a time (about 1 GB of RAM per page). | Consider OCR and extraction on the first 6 pages only, which bounds run time and memory. The page limit could then be relaxed. README note. |
| 12 | **One shared reviewer login is fine; include the credentials with the submission.** | Single reviewer login (planned). | Credentials go in the submission message, not the repo. |
| 13 | Review happens **within 3–4 days of submission. Keep the app and database running at least that long.** | Render starter web, standard worker; free Supabase pauses (C12). | Use paid or non-pausing tiers for at least 4 days after submission. T5 is still blocked on accounts. |
| 14 | **The repository can be public.** | Planned private, with Vaatun invited. | PO may switch to public. Check the bundle can be published (Vaatun allows it) and that no secrets are in the history. |
| — | Reviewers will upload policies, compare against the PDF and grid, and **ask for results to be traced back to the code**. No strict grading script. | Readable `.md` traces, citations, `file:line`-level code. | Make sure the README maps each trace step to its module. |

## Applied (2026-11-22)

- **#1 dates:** `GRID_DATE_POLICY` now defaults to `strict`. A policy outside the grid's stated period is
  `unsupported`, and the reason gives both dates. A grid that states no period is still used (the trace
  says so). An unreadable policy date gives `ambiguous` only when nothing else makes the policy
  `unsupported`. Effect on the samples: Reliance is now `unsupported` (policy from 23 Dec 2025, grid
  "Jan-26").
- **#6 business type:** the engine tries every business type when it is the only missing fact; equal
  rates → resolved with a trace note, otherwise `ambiguous`.
- **#11 pages:** only the first `READ_PAGES` pages are OCR'd and extracted. The default is 20, not 6,
  because the samples contradict "first 5–6 pages": Tata AIG prints its insurer name only on page 12 and
  Reliance its previous insurer on page 13 (with 6 pages both samples got worse). Worth raising with
  Vaatun at review; uploads may have up
  to 200 pages; `meta.pagesRead` and `meta.pageCount` are recorded.
- **#2 scope:** no code change needed; uncovered policies already return `unsupported` with the reason.
  Whether to finish the rest of T15 is the PO's decision (see the session's recommendation).
- **#12–#14** (login, hosting, public repo) are deployment steps for T5; **#10** still needs a key.
