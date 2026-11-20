---
change: 2026-11-20-brokerage-rate-agent
status: draft
owner: Soumitra Rai (product owner)
author: Soumitra Rai
risk: high
tracker: ""
---
# Intent: Brokerage rate agent (Vaatun INS/001)

Sources, in precedence order: `insurance-rater-agent-challenge/challenge.md` (official brief) >
`BRIEF.md` v2 > anything assumed earlier. Where they disagree, the conflict is flagged below, not
resolved silently.

## Problem

My submission to the Vaatun INS/001 challenge ("Insurance Rater Agent"). A broker cannot tell, from a
motor policy PDF alone, what commission (brokerage) percentage the insurer pays on it. Each insurer
publishes a commission grid in its own format: XLSX workbooks with dozens of sheets, or a PDF of zone
and slab tables. Lookups depend on RTO/zone, make/model, fuel, CC, vehicle age, policy type, business type,
NCB, premium slabs and footnotes. Reading those by hand is slow, error-prone and hard to audit, and a
black-box answer can't be trusted.

Reviewers judge the submission on whether it gets the rate right **or refuses correctly**, and whether
every step can be inspected. In challenge.md's words: "The strongest submission is not necessarily the one
that always returns a number."

## Proposed outcome

A hosted web app. A reviewer signs in, uploads a motor policy PDF they've never shown me, and sees:

- the policy facts the app read, each with the page it came from and how sure the app is about it;
- the OD and TP commission rates, reported separately and each marked applicable or not applicable,
  or an evidence-backed `unsupported` / `ambiguous` result explaining exactly which rule is missing,
  declined, contradictory or out of scope;
- an ordered, plain-language decision trace in which every fact, mapping and rate links to its exact source;
- a confidence level with a short reason.

Every earlier upload and its analysis is still there after refresh, reopen, sign-out/in, restart and
redeploy.

## Success criteria

How we'll know it worked. These are observable, not designs.

1. **Baseline gate passes.** At the hosted URL, an unseen private-car policy PDF uploaded in the browser
   returns a result, and that run (PDF and analysis) is still listed and openable after each of: browser
   refresh, closing and reopening, sign-out/in, server restart, and redeploy. Each event is demonstrated
   and documented in the README.
2. **The four samples behave as the test bench expects** (behaviour, not hard-coded answers):
   1. HDFC ERGO comprehensive: geography mapped to a zone, then the OD rate selected by zone × OD premium
      slab × fuel × NCB from the PDF grid.
   2. Go Digit SATP: TP-only bucket found by RTO cluster × fuel/CC segment; OD not applicable.
   3. Reliance comprehensive: model identified, segment mapped, footnote/exception obeyed.
   4. Tata AIG SATP: no supported rate, proven with evidence (a TP-only coverage gap) and reported as a
      refusal, not a guess.
3. **Every result is fully traceable.** Each extracted fact cites file + page. Each mapping and rate cites
   its source in that source's own format: XLSX gives file + exact sheet name + cell/range; a PDF grid gives
   file + page + table row. A reviewer can open the cited cell or row and see the same value.
4. **Deterministic resolution is proven by tests.** The same extracted facts always give the same result.
   The rating logic has unit tests covering resolved, unsupported, ambiguous, SATP and footnote/exclusion
   paths. The storage layer has tests showing runs persist and reload.
5. **Every covered motor product works (A1).** For each product a supplied grid covers, a policy of that
   product resolves or refuses with evidence from its own sheet. No product is refused just because it
   wasn't normalised.
6. **Unseen policies work.** Extraction and grid normalisation are general code that reads the original
   grid files. A policy from one of the four insurers that isn't a sample resolves or refuses with
   evidence, and a policy from an unsupported insurer or product returns `unsupported` with the reason.
7. **Submission is complete.** Hosted URL, repo, README (setup/run/deploy, where PDFs and analyses are
   stored and how they persist across each event), a short note on architecture, assumptions, failure
   modes and trade-offs, and committed structured outputs plus traces for all four samples that are easy to
   find. Emailed to careers@vaatun.com, subject "Insurance Rater Agent Challenge Submission", with
   credentials.

## Affected users and systems

- **Vaatun reviewers:** the only real users. They upload PDFs, read results, and judge the submission.
- **Me (solo):** I hold every sdlc role.
- **Policies:** any motor policy PDF from any insurer (A1), text-based or image-only (B2).
- **Inputs:** the starter bundle `insurance-rater-agent-challenge/`: 4 sample policy PDFs, 3 XLSX grids
  (Go Digit, Reliance, Tata AIG) and 1 PDF grid (HDFC ERGO), verified against `MANIFEST.json`.
- **External services (decided below):** a hosting platform, Supabase (Postgres + Storage + Auth), and an
  extraction LLM.

## Constraints

### Non-negotiables

1. **The LLM does extraction only.** Grid selection, mapping, matching and exceptions are plain,
   deterministic code: reproducible, unit-tested, explainable.
2. **Never infer through** a missing, declined, contradictory or out-of-scope rule. Return `unsupported`
   or `ambiguous` with the evidence instead. An exception (footnote, decline, exclusion, T&C) overrides an
   apparently matching cell.
3. **Uncertainty is preserved.** An unknown or low-confidence fact stays visible as such and is never
   guessed into a value.
4. **Stand-alone TP: OD is "not applicable", never 0%.** Each rate applies only to its own premium
   component, and no rate is applied to the whole premium.
5. **No hard-coded sample answers.** No value, fixture, test expectation or code branch is keyed to the
   four sample files' expected results. Grids are normalised from their original formats in code.
6. **Exact citations for every fact, mapping and rate.** Policy facts: file + page. XLSX: file + sheet +
   cell/range, with sheet names cited byte-for-byte (e.g. `'4W  RTO'` with two spaces, `'School & Staff Bus '`
   with a trailing space). PDF grid: file + page + table row. "Found in the grid" is never a citation.
7. **Business type rule:** same current and previous insurer means renewal.
8. **The bundle is read-only.** `insurance-rater-agent-challenge/` is never edited, moved or renamed
   (protected path in `sdlc.config.json`). It is committed as-is, packaged with the deployment, and
   verified against `MANIFEST.json` in a test.
9. **Upload happens in the deployed browser frontend.** A CLI may exist for development only.

### Output contract

The result keeps the shape of the example JSON (BRIEF.md v2 §6, from the challenge page) so its keys stay
recognisable: `status` (`resolved` | `unsupported` | `ambiguous`), `facts`,
`rates.od` / `rates.tp` each with `applicable` and `ratePercent`, `trace[]` with `decision`,
`policyCitation` and `gridCitation`, and `confidence` with `level` and `reason`. It is only ever extended,
never reshaped, and it must carry **all** R1 facts (insurer, previous insurer and business type where
relevant, make/model, fuel, RTO, CC, manufacture year or vehicle age, policy type, NCB, premium breakup,
plus policy start/issue date per D1), each with its page citation and uncertainty. The bundle has no separate schema file. An earlier assumption
of a "task contract schema" was wrong and is withdrawn.

### Product-owner decisions

- **Stack:** FastAPI (Python) backend + React frontend. Repo commands go through `make`
  (see `sdlc.config.json`).
- **Hosting:** Render or Fly (pick in spec). It must stay awake and reachable for the whole review: no
  free-tier sleep or pause that a reviewer could hit.
- **Durable storage:** Supabase, with Postgres for analyses and run history and Supabase Storage for
  uploaded PDFs. Both sit outside the app containers, so runs survive restart and redeploy. The Supabase
  project must not auto-pause during review.
- **Auth:** a single reviewer login (email + password), with credentials sent in the submission email.
  History is the same before and after sign-out/in.
- **Confidence:** evidence-based levels (high / medium / low) with a reason. A fact's level comes from the
  quality of its evidence. The overall level is the weakest fact the rate actually depended on. Resolution
  itself either matches every dimension or it doesn't.

### Settled decisions (2026-11-20)

Sources: **A** = answered by the brief (challenge.md / challenge page), **B** = product-owner decision,
**D** = default pending Vaatun's reply. Each D item is a single documented switch, so it can be flipped
without code changes elsewhere. Every A, B and D item is listed in the README as an assumption or decision.

- **A1 Scope.** Review uploads can be any motor policy from any insurer (R/05 says "motor", not only
  private car). Anything the supplied grids don't cover is `unsupported`, with the reason. Don't assume only
  the four sample insurers or only private cars. **Full scope (product owner, 2026-11-20):** every motor
  product that a supplied grid covers (private car, two-wheeler, commercial vehicle, taxi, school/staff
  bus, and others found in the files) is normalised and resolved. "Covered but not built" is never an
  acceptable `unsupported` reason.
- **A2 Contradictions.** If two matching rows or footnotes give different rates, the result is `ambiguous`
  (a contradictory rule, R/04), citing both. Never pick one.
- **A3 Business type.** A missing or unclear previous insurer is flagged only when the selected grid
  actually uses business type (R/01 "where relevant"). Otherwise it stays unknown and doesn't block.
- **A4 Output keys.** The schema isn't fixed ("your schema may differ"), but the example's keys are kept for
  easy comparison: `status`, `facts`, `rates.od/tp {applicable, ratePercent}`,
  `trace[{decision, policyCitation, gridCitation}]`, `confidence {level, reason}`. Extend it, never rename.
- **A5 Stand-alone TP OD** is `{"applicable": false, "ratePercent": null}`. Never 0.
- **A6 Clarifying questions** are optional ("may" ask). Every run finishes with its own status. A genuinely
  ambiguous fact gives `ambiguous`, and an answer-and-rerun option may be offered on top of that, never
  instead of it.
- **A7 Outside LLM.** Uploaded PDFs may be sent to an outside LLM API for extraction (R/04). The README
  states that uploads go to that API.
- **A8 Access.** A single shared reviewer login is fine. Credentials go in the submission email.
- **B1 XLSX values.** Read stored (cached) cell values, not formulas, and document this in the README. Cite
  cells exactly as they appear. A cell with no stored value counts as missing, never recalculated or guessed.
- **B2 OCR is required.** None of the four sample policies has a text layer. Checked with `pdffonts` and
  `pdftotext`: 0 fonts and 0 characters on every page of all four (9, 15, 4 and 12 pages). Reading page
  images is therefore the main extraction path, not a fallback, and page citations must still work. (The
  HDFC ERGO grid PDF does have a text layer.)
- **B3 Quote verification.** Every extracted fact carries its page and the exact text it came from. Code
  checks that text against that page's text (the text layer, or the OCR output for image pages). A fact
  that fails the check is low confidence, and a fact that relies on OCR text is at most medium.
- **B4 OCR engine** *(decided last)*. The preference is local OCR first. The engine choice is the last
  design decision, so the extraction path must not depend on which engine is picked.
- **D1 Grid dates** *(default, switchable)*. The policy start/issue date is extracted as an R1 fact. If it
  falls outside a grid's stated period, the grid is still used, with a trace warning ("grid effective
  <date>; policy dated <date>; a newer grid may exist") and lower confidence. The result is `unsupported`
  only when the grid itself states an end date and the policy falls after it.
- **D2 Broker eligibility** *(default, switchable)*. The broker is assumed to qualify for every supplied
  grid's base rates ("Large Insurance Brokers", "Broking Premier"). Bonuses that depend on the broker's
  business volume (e.g. Go Digit's "Additional 2.5% CD2 … partners with volume of 10 Lac monthly",
  Reliance's volume slabs) are never added. They appear in the trace as "possible, not applied: depends on
  broker volume, which the policy can't show". Whether private-car sheets carry such bonuses too (seen
  mostly on commercial-vehicle sheets) is checked in spec.

Still waiting on Vaatun, not blocking: review timing (decides hosting tier and keep-alive) and repo
visibility. Until they reply, hosting must not sleep or pause, and the repo stays private.

### Deadline

- Submit by **2026-11-21** (within 24 hours of 2026-11-20). Build order: the baseline gate and the four
  sample traces first, then the remaining covered motor products (A1). Full A1 scope is attempted. If the
  deadline can't hold it, the product owner asks Vaatun for more time rather than cutting scope. Nothing is
  cut silently.

### Conflict flagged between sources

- BRIEF.md v2 R3 says mapping steps cite "file + sheet + cell/range". challenge.md requires PDF citations as
  file + page + table row, and HDFC ERGO's zone mapping lives in its PDF grid. **challenge.md wins:** every
  citation uses the format of the file it points into.

## Out of scope

- Customer pricing, premium calculation, or discounts. We find the broker's commission percentage only.
- Rupee commission amounts (optional; not committed to).
- Rating non-OD/TP components (roadside assistance, paid driver, CNG kit, etc.).
- Uploading new grids, or policy URLs (both optional in the brief).
- Multi-user accounts, roles or tenancy beyond the single reviewer login.

## Open questions

Product-owner questions are settled above under "Settled decisions". If a Vaatun reply contradicts a D item,
only that switch flips.

For spec (design), answered there with evidence from the files:

1. How to extract table rows from the HDFC ERGO PDF grid so each rate cites page + row.
2. Which sheets are in scope per insurer, confirmed by reading them. Guideline, T&C and checks sheets
   are possible exception sources.
3. Where each grid states its effective period, if anywhere. (Already seen: the HDFC ERGO grid says
   "Effective from 1st Feb'25" and states no end date.)
4. Exact field-level extension of the output schema, and the confidence rules.
5. Extraction LLM model and the upload size/page limits. The OCR engine (B4) is decided last, local first.
6. Render vs Fly, and the plan tiers that avoid sleep or pause.
7. Whether private-car sheets carry broker-volume bonuses (D2).
8. How D1 and D2 are exposed as switches, and where they are documented.
