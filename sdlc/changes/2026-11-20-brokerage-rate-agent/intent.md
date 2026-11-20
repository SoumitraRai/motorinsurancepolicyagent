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
5. **Unseen policies work.** Extraction and grid normalisation are general code that reads the original
   grid files. A policy from one of the four insurers that isn't a sample resolves or refuses with
   evidence, and a policy from an unsupported insurer or product returns `unsupported` with the reason.
6. **Submission is complete.** Hosted URL, repo, README (setup/run/deploy, where PDFs and analyses are
   stored and how they persist across each event), a short note on architecture, assumptions, failure
   modes and trade-offs, and committed structured outputs plus traces for all four samples that are easy to
   find. Emailed to careers@vaatun.com, subject "Insurance Rater Agent Challenge Submission", with
   credentials.

## Affected users and systems

- **Vaatun reviewers:** the only real users. They upload PDFs, read results, and judge the submission.
- **Me (solo):** I hold every sdlc role.
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
relevant, make/model, fuel, RTO, CC, manufacture year or vehicle age, policy type, NCB, premium breakup),
each with its page citation and uncertainty. The bundle has no separate schema file. An earlier assumption
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

### Strict interpretations (decided 2026-11-20, without waiting for Vaatun)

Submission is due within 24 hours (by 2026-11-21), so questions for the hiring team were answered by the
product owner with the stricter reading. Each is recorded in the README as an assumption.

1. **Grid effective dates.** Where a grid states an effective period, the policy start date must fall inside
   it, or the result is `unsupported`, citing the period. Where the grid states none, the trace records
   "effective period not stated" and overall confidence is capped at medium. The folder date is never used
   as evidence.
2. **Scope.** Only private-car policies from the four supplied insurers' grids can resolve. Any other
   insurer, vehicle class or product is `unsupported`, with the reason.
3. **XLSX values.** The workbook's cached values are authoritative, and the citation records any formula
   behind the cell. A cell with no cached value counts as missing, never recomputed or guessed.
4. **Grid eligibility.** The supplied grids are taken as applying to this broker. Conditions in
   guideline/T&C/checks sheets that depend on policy facts are enforced. Conditions that depend on
   broker-side facts the policy can't show are listed as assumptions, never silently ignored.
5. **Overlapping matches.** If more than one row, cell or exception applies and they disagree, the result
   is `ambiguous`, citing all of them.
6. **Unknown business type.** If the grid depends on business type and the policy doesn't establish it,
   the result is `ambiguous`. If the grid doesn't depend on it, the fact stays unknown and doesn't block.
7. **Output format.** Assume machine grading. The example JSON's keys and value types are kept exactly
   (`ratePercent` is a number), and extensions are additive only.
8. **Stand-alone TP OD** is `{"applicable": false, "ratePercent": null}`, with a not-applicable reason.
9. **No clarifying questions.** A genuinely ambiguous fact always gives `ambiguous` with the evidence.
10. **Data minimisation.** Uploaded PDFs go only to our storage and the extraction LLM API, with no other
    third party. OCR for scanned pages runs locally. The README discloses where data goes.
11. **Extraction** (settles the earlier open question): text is pulled from the PDF first, image-only pages
    are OCR'd locally, and the LLM extracts from page-tagged text. Code checks every cited quote against
    that page's text. An unverified fact is low confidence, and an OCR-derived fact is at most medium. Upload
    size and page limits are explicit, set above the largest sample, and enforced with a clear error.
12. **Access.** One shared reviewer login, with credentials sent in the submission email.
13. **Uptime.** The review window is unknown, so the app and database run on tiers that don't sleep or pause.
14. **Repo.** The repo stays private, because the bundle contains real insurer grids. Access is granted to
    Vaatun by invitation at submission.

### Deadline

- Submit by **2026-11-21** (within 24 hours of 2026-11-20). Scope that endangers the baseline gate or the
  four sample traces is cut first.

### Conflict flagged between sources

- BRIEF.md v2 R3 says mapping steps cite "file + sheet + cell/range". challenge.md requires PDF citations as
  file + page + table row, and HDFC ERGO's zone mapping lives in its PDF grid. **challenge.md wins:** every
  citation uses the format of the file it points into.

## Out of scope

- Customer pricing, premium calculation, or discounts. We find the broker's commission percentage only.
- Rupee commission amounts (optional; not committed to).
- Rating non-OD/TP components (roadside assistance, paid driver, CNG kit, etc.).
- Products other than private cars, unless a grid sheet already covers them (they may be detected and
  returned as `unsupported`).
- Uploading new grids, or policy URLs (both optional in the brief).
- Multi-user accounts, roles or tenancy beyond the single reviewer login.

## Open questions

Product-owner questions are all settled above under "Strict interpretations". Questions sent to Vaatun
(if any) don't block. If a reply contradicts a strict interpretation, it reopens that item only.

For spec (design), answered there with evidence from the files:

1. How to extract table rows from the HDFC ERGO PDF grid so each rate cites page + row.
2. Which sheets are in scope per insurer, confirmed by reading them. Guideline, T&C and checks sheets
   are possible exception sources.
3. Where each grid states its effective period, if anywhere.
4. Exact field-level extension of the output schema, and the confidence rules.
5. Extraction LLM model and the upload size/page limits.
6. Render vs Fly, and the plan tiers that avoid sleep or pause.
