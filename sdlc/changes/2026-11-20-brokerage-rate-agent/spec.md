---
change: 2026-11-20-brokerage-rate-agent
status: accepted
owner: Soumitra Rai (product owner)
author: AI coding assistant
risk: high
tracker: ""
skills_applied: [security-policy@unreviewed-template, compliance-policy@unreviewed-template, secure-api-review@unreviewed-template, ux-standards@unreviewed-template, brand-guidelines@unreviewed-template]
intent_commit: f8579cd52cabdb518100acedad6e2af3a56ad9a3
---
# Spec: Brokerage rate agent (Vaatun INS/001)

Sources, in precedence order: `insurance-rater-agent-challenge/challenge.md` > `BRIEF.md` v2 >
`intent.md` (accepted at `f8579cd`). Intent decisions are cited as **A1–A8 / B1–B4 / D1–D2** and
intent non-negotiables as **NN1–NN9**. Grid facts below were read from the original files with
openpyxl (cached values, B1), pdfplumber/pdftotext, and the OCR spike, in throwaway scratch code. Rates are
described by structure only: no expected answer for any sample appears in this spec (NN5).

**Amended 2026-11-20 by PO: OpenRouter + local fallback (no Anthropic key).** Extraction goes through a
pluggable extractor: OpenRouter's OpenAI-compatible API by default (model chosen by the PO through
`EXTRACTION_MODEL`), with a local rule-based extractor whenever no key or model is set, or the call fails.
The run records which extractor ran. `status: accepted` is unchanged; affected text is marked "(amended)".

## Flagged concerns

Every row is a decision the product owner (PO) or tech lead (TL) must make before plan. Both roles are
held by Soumitra Rai. All 13 were decided on 2026-11-20 ("accept all recommendations"); decisions are recorded per row.

| # | Concern | Policy / skill | Owner | Decision |
|---|---------|----------------|-------|----------|
| C1 | **HDFC ERGO "premium slab" may be broker volume, not the policy premium.** The grid footnote reads "Slab will be calculated basis comprehensive + SAOD GWP on PVT CAR (SATP premium is excluded for slab achievement)". "GWP" and "achievement" suggest the broker's book, which D2 forbids us to assume. BRIEF §5's test bench reads it as "OD premium slab". **Recommend:** use the policy's own OD premium as the slab key (test-bench reading), quote the footnote in the trace, and cap confidence at medium. The alternative is `ambiguous` for every HDFC ERGO private-car policy. | intent NN2, D2 | PO || Accepted: policy OD premium is the slab key; footnote quoted in trace; confidence capped at medium. (Soumitra Rai, PO/TL, 2026-11-20) |
| C2 | **"X% lesser" wording is ambiguous.** Reliance `PRIVATE CAR COMP, SAOD & STP`!H3: "Payout for < 1000 CC, PO will be 5% lesser than the above Grid". This could mean percentage points or a relative 5%. Similar wording appears in other T&C cells. **Recommend:** percentage points (the usual Indian broker reading), recorded as an assumption in the README and the trace, and behind the same kind of switch as D1/D2. The alternative is `ambiguous` whenever such a line applies. | NN2, A2 | PO || Accepted: percentage points, behind switch `LESSER_PERCENT_MEANS=points`. (Soumitra Rai, PO/TL, 2026-11-20) |
| C3 | **The grid publishes no TP rate for package/comprehensive policies.** HDFC ERGO's grid has only OD/package columns. Reliance's sheet says "payout will made on OD Premium". Tata AIG `Pvtcar`!F2 says "Package/SAOD % on OD Premium; SATP % on Net Premium". The policy's TP component exists, but no rate is published for it. **Recommend:** `tp: {applicable: true, ratePercent: null, reason: "grid publishes no TP rate for this policy type"}` with the grid cell cited, and status decided by OD alone (`resolved` if OD resolves). The alternative is `unsupported` for the whole run, which would refuse every package policy in three of the four grids. | A4, A5, R2 | PO || Accepted: TP `applicable: true, ratePercent: null` with reason and cited cell; status set by OD. (Soumitra Rai, PO/TL, 2026-11-20) |
| C4 | **Every sample policy is image-only (B2), so B3 caps every fact at medium**, and no run on these four can ever be "high". Reviewers will see "medium" everywhere. **Recommend:** keep B3 as written (honest), and explain the cap on screen and in the README. The alternative is allowing "high" when both OCR engines and the LLM agree exactly. | B3 | PO || Accepted: keep the B3 cap; explain it on screen and in the README. (Soumitra Rai, PO/TL, 2026-11-20) **Amended 2026-11-23 by PO:** every real policy will be scanned, so the cap is lifted. A scanned fact is `high` when both OCR engines read the same value independently; a result is `high` when ≥ 90% of the facts it used are `high` and every fact that picked the rate row is at least `medium` (see SR23). |
| C5 | **Undefined declines in Go Digit `4W SATP` notes.** Column F carries notes such as "Few RTOs for 1000-1500CC segment are declined" without naming the RTOs. The rule is incomplete. **Recommend:** a policy in a cluster and band covered by such a note is `ambiguous`, citing the note, never resolved by assuming the RTO isn't one of the "few". | NN2 | PO || Accepted: `ambiguous`, citing the note. (Soumitra Rai, PO/TL, 2026-11-20) |
| C6 | **Gaps at band boundaries.** Go Digit uses `Petrol<1000` and `Petrol>1000`, and `<10` and `>10` for age. HDFC ERGO uses `<10k` and `>10-50k`. Exactly 1000 cc, age 10, or ₹10,000 falls in no band. **Recommend:** a value in no band is `ambiguous`, never rounded into the nearer band. | NN2, A2 | PO || Accepted: a value in no band is `ambiguous`. (Soumitra Rai, PO/TL, 2026-11-20) |
| C7 | **Go Digit's rate column is titled "Max CD2"**, which could be a ceiling rather than the rate payable. **Recommend:** report it as the rate, labelled in the trace as "insurer's published maximum (Max CD2)", and assumed in the README. The alternative is `unsupported` for all Go Digit grids. | NN2 | PO || Accepted: report as the rate, labelled "insurer's published maximum (Max CD2)"; README assumption. (Soumitra Rai, PO/TL, 2026-11-20) |
| C8 | **Tata AIG has no make/model → segment table** in any of its 7 sheets, including the hidden `cv checks` and `pci checks`. `Pvtcar` rows need a segment (Mini, Compact, Mid Size, …). Our own knowledge of which models are "Mini" would be inference. **Recommend:** if the policy doesn't print the segment, the result is `unsupported`, citing the absence of a mapping. This is consistent with the test bench's Tata case expecting a refusal; we don't target that answer, it follows from the rule. | NN2, NN5 | PO || Accepted: no printed segment → `unsupported`, citing the missing mapping. (Soumitra Rai, PO/TL, 2026-11-20) |
| C9 | **Full A1 scope is large.** About 20 sheets beyond private car (CV, HCV, taxi, school/staff bus, two-wheeler, SAOD flexi), each with its own layout. That doesn't fit 24 hours with certainty. Per intent's Deadline: attempt everything, and if time runs short the PO asks Vaatun for more time. **Recommend:** build in the order of the Build order section below, so the baseline gate and the four samples are safe first. | intent A1, Deadline | PO || Accepted: build order baseline → four samples → rest of A1; ask Vaatun for time if short. (Soumitra Rai, PO/TL, 2026-11-20) |
| C10 | **Reviewer uploads may contain real personal data** (names, addresses, registration numbers). They are stored in Supabase and sent to the extraction LLM API (A7; amended: OpenRouter, when configured). The security policy template says new storage or transfer of restricted data needs a flagged concern. **Recommend:** treat uploads as restricted, use a private bucket, disable signups, keep personal fields out of logs, disclose this in the README, and keep data for the review period only. | security-policy, A7 | PO (as data protection owner) || Accepted: restricted data controls as recommended; disclosed in README. (Soumitra Rai, PO/TL, 2026-11-20) |
| C11 | **The policy skills are unfilled templates.** All five organisation policy files (security, compliance, brand, UX, API review) have placeholders and no review date, so they were applied in spirit only (generic controls). **Recommend:** accept them as applied for this submission and note it in the README's assumptions. | all policy skills | PO (as policy owner) || Accepted: templates applied in spirit; noted in README assumptions. (Soumitra Rai, PO/TL, 2026-11-20) |
| C12 | **Paid hosting tiers.** Intent requires no sleep or pause, which needs paid Render and Supabase plans. The cost depends on plan prices at sign-up and isn't stated here. **Recommend:** Render paid web service and worker, plus Supabase Pro, for the review window. | intent decisions (uptime) | PO (budget) || Accepted: Render paid web + worker, Supabase Pro for the review window. (Soumitra Rai, PO/TL, 2026-11-20) |
| C13 | **secure-api-review asks for `scripts/check-endpoints.sh` output, but that script doesn't exist in this repo.** **Recommend:** replace it with an automated test that every route except `/health` returns 401 without a valid JWT (AC19). | secure-api-review | TL || Accepted: AC19 replaces `check-endpoints.sh`. (Soumitra Rai, PO/TL, 2026-11-20) |

## Summary

A hosted web app where a Vaatun reviewer signs in with the shared reviewer login and uploads any motor
policy PDF, text-based or scanned. In the background, the app reads every page with two local OCR engines.
An extractor (an LLM via OpenRouter, or local rules as the fallback) proposes the R1 facts, each with a
page and a verbatim quote, and code checks every quote against
the OCR text. Plain deterministic code then picks the insurer's grid, maps facts into that grid's
vocabulary, matches the row, and applies footnotes and exceptions. The run ends as `resolved`,
`unsupported` or `ambiguous`, with OD and TP reported separately (stand-alone TP OD is always "not
applicable"), every step cited to a file + page, or file + sheet + cell, or file + page + table row, and
an evidence-based confidence. Runs (PDF + analysis) live in Supabase and survive refresh, reopen,
sign-out/in, restart and redeploy.

## Requirements

Each requirement traces to intent (`I:` = section of intent.md).

**Input and access**
- **SR1** Upload happens in the deployed browser frontend. It accepts one PDF up to **25 MB** and **60
  pages**; anything else is rejected with a clear message. (I: NN9; open Q5. The largest sample is
  10.4 MB and 15 pages; the API limit is 32 MB per request.)
- **SR2** Sign-in is required. One shared reviewer account exists, sign-ups are disabled, and every API
  route except `GET /health` requires a valid session token. (I: A8; secure-api-review)
- **SR3** Every run, with its original PDF and completed analysis, stays listed and openable after
  refresh, closing and reopening, sign-out/in, server restart and redeploy. (I: success criterion 1; R6)

**Extraction (LLM for extraction only, NN1)**
- **SR4** Each page is rendered and OCR'd by RapidOCR (main) and Tesseract (cross-check). A text layer is
  used when present. The engine, its version and the text are kept per page. (I: B2, B4)
- **SR5** The LLM returns, per R1 fact, a value or `unknown`, the 1-based page, and a verbatim quote. The
  facts are: insurer, previous insurer, business type evidence, make, model/variant, fuel, RTO
  code/location, CC, manufacture year, registration year, policy type, NCB %, OD premium, TP premium,
  other premium lines, policy start date, and issue date. The LLM never chooses a grid, rate or mapping.
  (I: R1, NN1, D1)
- **SR6** Code checks each quote against the cited page's text, ignoring whitespace and case. The result
  per fact is `verified_both`, `verified_one`, `unverified` or `not_found`. (I: B3)
- **SR7** Deterministic normalisation turns quoted values into canonical forms: RTO code (e.g.
  `HR-26-FB-8239` → `HR26`), fuel enum, CC integer, money as decimal ₹, NCB %, dates as ISO. If parsing
  fails, the fact is `unknown`, never guessed. A placeholder date (e.g. `0001-01-01`) is `unknown`. (I: NN3)
- **SR8** Business type comes from code. Same current and previous insurer → `renewal`. Different insurer
  → `rollover`. "New" only when the policy states new or first registration. Otherwise `unknown`.
  (I: NN7, A3)
- **SR9** Policy type comes from the schedule's title and premium sections only. Watermark or background
  text is ignored. Text that contradicts the title, such as a "Liability Only" title with an OD premium
  line, makes the run `ambiguous`. (I: B4 spike finding)
- **SR10** When a policy shows more than one NCB figure, the lookup NCB is the one applied in the current
  premium computation. Others are recorded as `previousNcb`. If no figure is clearly applied, the result
  is `ambiguous`. (I: B4 spike finding)

**Grids (deterministic, R4)**
- **SR11** At startup, grids are loaded only from `insurance-rater-agent-challenge/raters/`, after SHA-256
  verification against `MANIFEST.json`. A mismatch stops the worker. Bundle files are never written.
  (I: NN8)
- **SR12** XLSX is read with cached values only (`data_only=True`). A formula cell with no cached value is
  missing. Sheet names are kept byte-for-byte. Error values (`#REF!`), subtotal rows (e.g. `Pvtcar`!567
  `=SUBTOTAL(...)`) and helper concatenation columns (`=B59&C59&D59`) are never treated as data.
  (I: B1, NN6)
- **SR13** The HDFC ERGO PDF grid is read from its text layer with word coordinates and rebuilt into
  tables. Each rate cell carries page, table name (e.g. "Zone 1"), row label (e.g. `<10k`) and column path
  (e.g. Package › Petrol › NCB & N-NCB). (I: open Q1)
- **SR14** Every motor product a supplied grid covers is normalised into one common rule model (see
  Design). In scope by insurer:
  - Go Digit: `4W SATP`, `4W New Business 1+3`, `4W  RTO`, `TW 1+1 & SATP`, `TW 1+5`, `2W Grid 5+5`,
    `TW SAOD with Flexi Options`, `2W RTO's`, `CV Grid (excl. HCV)`, `HCV GRID`,
    `TAXI Segments and Location wise`, `CV RTO Mapping`, `School & Staff Bus `, `School & Staff Bus RTO`.
  - Reliance: `PRIVATE CAR COMP, SAOD & STP`, `FEB'26 - Grid`, `TW SCOOTER GRID`, `RTO List`,
    `Make Model wise segment`, `Enabler, PO Guidelines & T&C`.
  - Tata AIG: `Pvtcar`, `CV`, `TW`, `General Guidelines`.
  - HDFC ERGO: the 2-page private-car grid.
  - Out of rule scope, with reasons: Reliance `Short Term Taxi` (empty) and `Contest` (an image only;
    listed as "not machine-readable"); Tata AIG `cv checks` and `pci checks` (hidden pivot checks of the
    main grid, not rules); Tata AIG `Pvtcar_Extended Warranty` (not OD/TP). (I: A1)
- **SR15** Grid selection is by insurer, then product (vehicle class), then policy type
  (package/comprehensive, SAOD, SATP), then business type where the grid splits on it. No grid for the
  combination → `unsupported`, naming what was searched. Examples: Go Digit has no 4W package grid for
  old business; Reliance's private-car sheet is titled "Old Business" and has no new-business grid.
  (I: A1)
- **SR16** Mapping uses only the grid's own tables (RTO → zone/cluster; make/model → segment) and cites
  the mapping row. When the grid's mapping and the policy's printed location disagree, the grid's mapping
  wins and the disagreement is noted in the trace. Example: Reliance `RTO List` maps `UP-16` to Region_City
  "Delhi" while the policy prints "UTTAR PRADESH - Noida". A required mapping that's missing →
  `unsupported`. (I: NN2, C8)
- **SR17** Matching selects rows where **every** dimension the grid uses matches. Zero matches →
  `unsupported`. More than one match with different rates → `ambiguous`, citing all of them. A fact a
  matched dimension needs that is `unknown` → `ambiguous`. A value at a band gap → `ambiguous` (C6).
  (I: A2, NN2)
- **SR18** Exceptions (footnotes, T&C lines, declines, notes) are parsed from their cells by code into
  typed rules:
  - a condition on policy facts, with an effect (reduce/add/decline/override);
  - a broker-side condition, which D2 never applies (e.g. "2.5 lakh monthly volume", synergy mix, "GWP
    based rule", volume slabs);
  - not applicable to this product or policy.

  Exceptions are applied before the answer and override a matching cell. A T&C line that falls within
  the matched sheet's scope but that the parser can't classify makes the run `ambiguous`, citing the line.
  (I: NN2, D2)
- **SR19** D2 switch `BROKER_ELIGIBILITY=assume_base`, with `require_evidence` as the alternative. Base
  rates are used. Every broker-side bonus found in scope is listed in the trace as "possible, not
  applied: depends on broker volume, which the policy can't show". (I: D2)
- **SR20** D1 switch `GRID_DATE_POLICY=warn`, with `strict` as the alternative. Grid effective dates come
  from grid text, never folder names. Examples: HDFC ERGO "Effective from 1st Feb'25"; Tata AIG `Pvtcar`!F1
  "applicable from 1st Nov'25 policies"; Reliance "Pvt Car Old Business Grid- Jan-26" and "PO Grid for
  FEB '26"; Go Digit school bus "Applicable from 1st of Mar, 2026". A policy dated outside the stated
  period adds a warning and lowers confidence one level. `unsupported` only when the grid states an end
  date and the policy is after it. A grid with no stated date gets a trace note and no penalty. (I: D1)

**Output and confidence**
- **SR21** The result keeps the example JSON's keys (`status`, `facts`, `rates.od/tp.{applicable,
  ratePercent}`, `trace[].{decision, policyCitation, gridCitation}`, `confidence.{level, reason}`) and only
  adds keys (see Design). Grid values stored as fractions (Go Digit, Tata AIG, e.g. `0.295`) are converted
  to percent numbers in `ratePercent`, with the raw cell value kept. Rate rounding is never applied.
  (I: A4)
- **SR22** Stand-alone TP → `od: {applicable: false, ratePercent: null, reason}`, never 0. A published 0
  (e.g. Reliance `STP` column) is reported as `ratePercent: 0` with its cell, because it's the grid's stated
  value. (I: A5, NN4)
- **SR23** Confidence:
  - per fact: `high` if verified against a text layer; `medium` if verified by both OCR engines; `low`
    if one engine only or unverified; `unknown` if not found.
  - overall: the weakest fact the result depended on, lowered one level per D1 warning, and capped at
    medium when C1's assumption applies.
  - for `unsupported` and `ambiguous`: the weakest fact the refusal depends on.
  - `reason` names the weakest link. (I: B3, confidence decision)
  - **Amended 2026-11-23 by PO (C4):** per fact, also `high` when the quote is in both OCR engines' text
    and the value read from the cross-check engine's text alone is the same (`confirmed_both`). Overall:
    the share of used facts that are `high`; ≥ 90% → `high`, ≥ 70% → `medium`, else `low`, never below
    the weakest fact's level; `low` if a fact that picked the rate row (mapping, matched row, T&C
    condition) is below `medium`; then D1 warnings and caps as above. `reason` states the share and the
    weakest link. Applies to `unsupported` and `ambiguous` results too.
- **SR24** Every run is persisted as its exact result JSON, with the run's inputs: PDF SHA-256, engine
  versions, model id, grid manifest hash, and D1/D2/C2 switch values. A rerun of the same facts gives
  byte-identical resolution output. (I: success criterion 4)
- **SR25** Clarification (A6): an `ambiguous` result may list the facts that would settle it. The
  reviewer can supply them, which starts a new linked run marked "reviewer-supplied fact". The original
  run is never changed. (I: A6)

**Deliverables**
- **SR26** Structured outputs and traces for all four samples are committed under `samples/output/` (one
  JSON plus one readable `.md` trace each) and linked from the README. They're produced by running the
  real pipeline; nothing is hand-edited. (I: success criterion 7)
- **SR27** The README covers: setup, run and deploy; where PDFs and analyses are stored and how they
  persist across each R6 event; every A/B/D decision and C-row decision as assumptions; the D1/D2
  switches; that uploads go to OpenRouter and its upstream model provider when a key is set (amended);
  architecture, failure modes and trade-offs.
  (I: A7, success criterion 7)

## Design

### Approaches considered (decided here unless flagged)
1. **Grid normalisation.**
   - (a) One adapter per sheet layout into a common rule model. **Chosen**: deterministic, unit-testable
     per sheet, and every rule keeps its source cells.
   - (b) Generic table inference across all sheets. Rejected: layouts differ too much (14-sheet Go
     Digit, 70-column Tata AIG, PDF tables), and errors would be silent.
   - (c) LLM-normalised grids. Rejected: breaks NN1.
2. **LLM input.**
   - (a) Page images plus page-tagged OCR text, with quotes required to come from the OCR text.
     **Chosen**: the quote check (B3) needs the quote in OCR text, and the image lets the model read
     layout.
   - (b) The PDF document block only. Rejected: quotes might not match OCR text.
   - (c) The API's citations feature. Rejected: it can't be combined with structured outputs.
   - (amended) The provider is OpenRouter, not the Anthropic SDK; a local rules extractor is the fallback.
3. **Background processing.**
   - (a) A worker process polling a Postgres jobs table (`FOR UPDATE SKIP LOCKED`). **Chosen**: no
     extra service, and jobs survive restarts.
   - (b) Redis/Celery. Rejected: another service to keep awake.
   - (c) In-request processing. Rejected: 1–5 minutes per run (OCR spike).
4. **Hosting.**
   - (a) Render: Docker web service plus background worker, paid always-on. **Chosen**: simple deploy,
     with Tesseract and the ONNX model baked into the image.
   - (b) Fly.io with `min_machines_running=1`. Viable; slightly more operational work.

### User experience
Applies ux-standards and brand-guidelines (templates, C11). React SPA with one component library used
throughout, and design tokens for colour, type and spacing.

- **Sign in.** Email and password, labels always visible, inline errors ("Email or password is wrong.
  Try again."). After sign-in → History.
- **History** (home). One primary action: **Upload a policy PDF**. A table of runs, newest first:
  - file name, uploaded time, insurer, status badge (`resolved` / `unsupported` / `ambiguous` /
    `processing` / `failed`), OD and TP.
  - Empty state: "No policies yet. Upload a motor policy PDF to get its brokerage rate."
  - Loading: skeleton rows after 300 ms.
- **Upload.** Drag-and-drop or file picker, PDF only, with limits shown (25 MB, 60 pages).
  - Validation errors are inline and say what to do.
  - On success, the reviewer lands on the run page in `processing` state.
- **Run page.**
  - **Header:** status badge in text and colour, never colour alone. Plain-language one-line answer,
    e.g. "OD 12% · TP not published by grid" or "Cannot determine: no Tata AIG segment mapping for this
    model".
  - **Rates card:** OD and TP, each with applicability and reason.
  - **Confidence:** level and reason. Explains the OCR cap (C4).
  - **Warnings:** D1 dates, D2 "possible, not applied".
  - **Trace:** an ordered list. Each step shows the decision in plain words, a policy citation (opens the
    PDF at that page), and a grid citation (file · sheet!range, or file · page · table · row).
  - **Facts table:** value, page, quote, verification, confidence; `unknown` shown as "Not found".
  - **JSON tab:** raw result, with a download button.
  - **Clarify panel** (only for `ambiguous`, SR25).
- **Processing state.** Progress steps: OCR, extraction, checking quotes, resolving. Polling every 3 s,
  and the page survives refresh. Failure state: what failed plus a "Retry this run" button. Input is never
  lost.
- **Accessibility.** WCAG 2.2 AA:
  - full keyboard path (upload, table, tabs, citations);
  - status changes announced with `aria-live`;
  - 44 px touch targets;
  - focus order matches reading order.
- **Sign out.** Always visible. History is the same after signing in again (SR3).

### Data and interfaces
Applies security-policy and secure-api-review (templates, C11).

**API** (FastAPI, JSON, every route requires a Supabase JWT verified server-side, except `/health`).
Request bodies are validated with Pydantic models that reject unknown fields.
- `POST /api/runs`: multipart upload of one PDF. Checks magic bytes, size and page count. Stores it
  in Storage, inserts `runs` and `jobs` rows, returns `202 {id}`. Audit: `run.created`.
- `GET /api/runs?cursor=`: paginated history for the caller.
- `GET /api/runs/{id}`: run status, result JSON, and page metadata.
- `GET /api/runs/{id}/pdf`: short-lived signed URL to the stored PDF.
- `POST /api/runs/{id}/retry`: re-queue a `failed` run. Audit: `run.retried`.
- `POST /api/runs/{id}/clarify`: body `{facts: {name: value}}`. Creates a linked run (SR25). Audit:
  `run.clarified`.
- `GET /health`: liveness only. Includes the grid manifest check and the DB check, and returns no data.

**Storage** (Supabase).
- Private bucket `policies/` with key `{run_id}/{sha256}.pdf`.
- Postgres:
  - `runs(id uuid, user_id, created_at, file_name, pdf_sha256, storage_key, page_count, status, result
    jsonb, error, parent_run_id, switches jsonb, versions jsonb)`
  - `jobs(id, run_id, state, attempts, locked_at, last_error)`
  - `pages(run_id, page_no, ocr_rapid text, ocr_tess text, text_layer text)`
  - `audit_events(id, actor, action, entity, at)`
- Migrations are SQL files under a `migrations/` path (protected path: TL plus a change ticket note).
- Row-level security limits rows to `user_id`.

**Result JSON** (extends the example; existing keys unchanged):
```json
{
  "status": "resolved | unsupported | ambiguous",
  "facts": {
    "rto": { "value": "HR26", "raw": "HR-26-FB-8239", "page": 1, "quote": "Registration No HR-26-FB-8239",
             "verification": "verified_both", "confidence": "medium",
             "policyCitation": "<file>.pdf · page 1" }
  },
  "rates": {
    "od": { "applicable": true, "ratePercent": 0.0, "reason": "...", "rawCellValue": "0.0",
            "gridCitation": "<grid file> · '<sheet>'!E40" },
    "tp": { "applicable": false, "ratePercent": null, "reason": "Stand-alone TP policy: OD not applicable" }
  },
  "trace": [
    { "step": 1, "kind": "extract | select | map | match | exception | date | broker_bonus | result",
      "decision": "plain-language sentence",
      "policyCitation": "<file>.pdf · page N",
      "gridCitation": "<file> · '<sheet>'!B14:C14  |  <file>.pdf · page 1 · table 'Zone 2' · row '<10k'",
      "citations": [ { "type": "xlsx", "file": "...", "sheet": "4W  RTO", "range": "B1609:F1609" } ],
      "warnings": [] }
  ],
  "confidence": { "level": "medium", "reason": "weakest link: ...", "cappedBy": ["ocr"] },
  "notApplied": [ { "rule": "...", "why": "depends on broker volume, which the policy can't show",
                    "gridCitation": "..." } ],
  "clarification": { "facts": ["manufactureYear"] },
  "meta": { "pdfSha256": "...", "extractor": "openrouter | rules", "model": "<EXTRACTION_MODEL or null>", "ocr": {"rapidocr": "x.y", "tesseract": "5.5.4"},
            "gridManifest": "<sha256 of MANIFEST.json>", "switches": {"GRID_DATE_POLICY": "warn",
            "BROKER_ELIGIBILITY": "assume_base", "LESSER_PERCENT_MEANS": "points"} }
}
```
(Values above illustrate shape only.)

- Citation strings are fixed formats:
  - policy: `<file> · page N`
  - XLSX: `<file> · '<sheet>'!<range>`, with the sheet name exact (spaces kept)
  - PDF grid: `<file> · page N · table '<name>' · row '<label>'`
- Structured `citations[]` carries the same data for tests.

**Common rule model** (in memory, built at worker start):
- `Grid{insurer, file, effectiveFrom?, effectiveTo?, product, sheets}`
- `MappingTable{kind: rto→zone|rto→cluster|model→segment, rows: [{key, value, cite}]}`
- `RateRule{product, policyType, businessType?, dimensions: {zone?, segment?, fuel?, ccBand?, ageBand?,
  ncb?, premiumSlab?, addOn?}, od?, tp?, cite}`
- `ExceptionRule{scope, kind: policy_condition|broker_side|out_of_scope|unclassified, condition, effect,
  text, cite}`

Bands are parsed from labels into explicit intervals, with open and closed ends recorded so C6 gaps can
be detected.

**Extraction call (amended).**
- OpenRouter chat completions over httpx (`POST https://openrouter.ai/api/v1/chat/completions`), model
  from `EXTRACTION_MODEL` (no model id is hard-coded; the PO picks a vision model with structured-output
  support).
- Structured output: `response_format` `json_schema` (per fact `{value|null, page|null, quote|null}`,
  `strict: true`), with `provider.require_parameters: true`. No sampling parameters are sent.
- Fallback: with no key or model, or on any error, timeout, rate limit, out-of-credit or schema violation,
  the local rules extractor runs (generic schedule labels over the OCR rows). `meta.extractor` records it.
- Input: page images plus page-tagged OCR text. The prompt tells the model to copy quotes exactly from
  the OCR text, and to return `null` rather than guess.
- No grid content is ever sent.
- The output is treated as untrusted and validated against the schema before SR6.

**Security controls.**
- Secrets (`OPENROUTER_API_KEY` (amended), Supabase service key, JWT secret) come only from host environment
  variables. Never in the repo or logs, and `.env*` is never written by an agent.
- Logs carry run ids and step names only. No fact values, quotes, names or registration numbers (C10).
- Rate limit uploads at 10 per minute per user.
- New dependencies are pinned with licences checked: RapidOCR (Apache-2.0), Tesseract (Apache-2.0),
  openpyxl (MIT), pdfplumber (MIT), pypdfium2 (Apache-2.0/BSD), FastAPI (MIT), httpx (BSD) (amended).
- Egress goes only to OpenRouter (when configured) and Supabase (amended).

### Integration with the existing codebase
Greenfield. The repo today holds only the process scaffold (build, test and lint commands via `make`)
and the read-only bundle. The application adds:
- a Python backend: API, worker, extraction, grids, resolution;
- a React frontend;
- a root `Makefile` that keeps `make build/test/lint/format/run` working;
- a `Dockerfile` with Tesseract and the RapidOCR models.

Module boundaries (names only; files and order are Stage 3):
- `extraction/` (OCR, LLM, verification, normalisation): the only place an LLM is called.
- `grids/` (manifest check, one adapter per sheet layout, rule model).
- `resolve/` (select, map, match, exceptions, confidence): pure functions over facts and rules, no I/O.
- `storage/` (Supabase DB and Storage behind an interface, so tests use a real local Postgres plus a
  fake object store).
- `api/` and `worker/`.

The `sdlc-deploy.yml`, `sdlc-control-band.yml`, `sdlc-mention.yml` and `sdlc-spec-on-intent.yml`
workflows must be disabled or made manual-only before the first push (memory note; outside this spec's
code).

### Build order (for C9; ordering, not a plan)
1. Baseline gate: upload, worker, storage, history, auth, deploy.
2. The four sample paths: HDFC ERGO PDF grid, Go Digit 4W SATP, Reliance private car, Tata AIG `Pvtcar`.
3. The rest of A1: two-wheelers, then CV/taxi/bus.

## Non-functional requirements
- **Latency:** a 15-page policy reaches a final state within 5 minutes at p95. Pages are OCR'd in
  parallel, and the UI stays responsive throughout.
- **Availability:** no sleep or pause for the review window (C12). `/health` is checked by the host.
- **Durability:** PDFs and results live only in Supabase (managed Postgres with backups, plus Storage).
  Containers are stateless, so any container can be killed at any time without data loss (R6).
- **Reproducibility:** resolution is a pure function of the facts, the grid files and the switches.
  Identical input gives identical output (SR24).
- **Data classification:** uploads and extracted facts are restricted (C10). They're retained for the
  review period, then deleted on PO instruction, and the README says so.
- **Audit:** every state change writes `audit_events` (actor, action, entity, timestamp).
- **Cost:** one extraction call per run. OCR is local.

## Acceptance criteria
Each becomes an automated test unless marked (manual).

**Bundle and grid loading**
- **AC1** The MANIFEST test passes for all 10 files, and a modified copy of any rater file makes worker
  start-up fail.
- **AC2** For every in-scope sheet (SR14), the adapter loads without error. Every rule's citation points
  to a cell or PDF row whose stored value equals the rule's raw value. This is property-tested over all
  rules.
- **AC3** Sheet names in citations equal the workbook's names byte-for-byte, including `'4W  RTO'` and
  `'School & Staff Bus '`.
- **AC4** A formula cell with no cached value (e.g. `School & Staff Bus ` has 7) produces a "missing"
  marker and never a number. `#REF!` and `SUBTOTAL` rows produce no rules.

**Resolution rules** (synthetic facts, so no test is keyed to a sample's expected rate)
- **AC5** Resolver unit tests:
  - all dimensions match → `resolved`;
  - no row → `unsupported`;
  - two rows with different rates → `ambiguous`, citing both;
  - a dimension's fact `unknown` → `ambiguous`;
  - a band-gap value (e.g. exactly 1000 cc) → `ambiguous`;
  - a missing mapping → `unsupported`.
- **AC6** Stand-alone TP input → `rates.od == {applicable: false, ratePercent: null, …}` for every
  insurer. No code path can emit `od.ratePercent == 0` for a stand-alone TP policy.
- **AC7** Exception tests:
  - a policy-condition footnote overrides a matching cell and the trace cites it;
  - a broker-side bonus is never added and appears in `notApplied`;
  - an unclassified in-scope T&C line → `ambiguous`.
- **AC8** D1: a policy dated before a grid's "effective from" → warning plus one-level confidence drop.
  `strict` → `unsupported`. No stated date → note only.
- **AC9** The D2 and C2 switches change behaviour as documented, and the switch values appear in
  `meta.switches`.
- **AC10** Business type: same insurer → `renewal`; different → `rollover`; missing previous insurer when
  the grid doesn't split on business type → doesn't block (A3).
- **AC11** Resolution determinism: the same facts JSON resolved twice gives byte-identical output.

**Extraction**
- **AC12** Quote verification: a quote present in both engines' text → `verified_both`; in one →
  `verified_one`; absent → `unverified`, with confidence low. Whitespace and case are ignored.
- **AC13** Normalisation: `0001-01-01` → `unknown`; `HR-26-FB-8239` → `HR26`; ₹ amounts parsed; an OCR
  `%` adjacent to a rupee amount is never parsed as a rate.
- **AC14** SR9 policy type: a page with a "Liability Only" watermark but a package title and an OD
  premium section → `comprehensive`; contradictory titles → `ambiguous`.
- **AC15 (amended)** LLM calls happen only in `extraction/providers/`: no module imports an LLM SDK,
  `httpx` is used only in `extraction/providers/`, `storage/` and `api/`, and `grids/`/`resolve/` never
  import extraction. Checked by a test that scans imports. Every provider failure falls back to rules.

**Storage and API**
- **AC16** Storage boundary: a run written through the storage interface is read back identically after
  a new client and a new connection, which simulates a restart. The PDF bytes' SHA-256 matches.
- **AC17** Signed PDF URLs expire, and another user's run returns 404.
- **AC18** API: an upload over 25 MB, over 60 pages, or not a PDF → 4xx with a message. A valid upload →
  202, and the run reaches a final state through the worker.
- **AC19** Every route except `/health` returns 401 without a valid JWT (replaces `check-endpoints.sh`,
  C13).
- **AC20** No log line contains extracted fact values or quotes. This is checked by running the
  pipeline on a sample with a capturing log handler.

**End to end**
- **AC21** For each of the 4 samples, a pipeline run produces:
  - a schema-valid result;
  - every `gridCitation` resolving to a real cell or row (AC2's checker);
  - SATP samples with `od.applicable == false`;
  - committed outputs under `samples/output/`.

  The test asserts structure and citations only, never a specific rate.
- **AC22** (manual, recorded in the README with timestamps) On the hosted URL, an unseen policy is
  uploaded. The run is still listed and openable after each of: refresh, closing and reopening the
  browser, sign-out/in, a service restart, and a redeploy.
- **AC23** (manual) Keyboard-only walkthrough of sign-in → upload → run page → citation → JSON download.
  Screen-reader announcement of status change.

## Open questions carried forward

From intent.md "Open questions":
1. **HDFC ERGO table-row extraction.** Answered in SR13: the text layer plus word coordinates, cited as
   page · table · row.
2. **Sheets in scope per insurer.** Answered in SR14, with excluded sheets and reasons.
3. **Grid effective periods.** Answered in SR20 (HDFC ERGO, Tata AIG, Reliance, Go Digit school bus
   stated; others not stated).
4. **Output schema extension and confidence rules.** Answered in the result JSON and SR23. The OCR cap
   consequence is raised as C4 (PO).
5. **Extraction model and upload limits.** Answered (amended): OpenRouter, model set by the PO via
   `EXTRACTION_MODEL`, with the local rules fallback (extraction call above); limits
   25 MB and 60 pages (SR1).
6. **Render vs Fly and tiers.** Answered: Render (Approaches 4). Tier cost raised as C12 (PO).
7. **Broker-volume bonuses on private-car sheets (D2).** Answered:
   - Go Digit 4W sheets: none found.
   - Reliance: synergy enablers (broker business mix) apply across retail and are broker-side. The
     private-car T&C has policy-level lines (add-on bundle +2.5% "if sourced", <1000 CC reduction,
     standalone ZD −2.5%).
   - Tata AIG: "GWP based Rule … Incremental COA" is broker-side.
   - HDFC ERGO: the slab footnote is raised as C1.
   - Broker-side items go to `notApplied`, per SR19.
8. **D1/D2 switches.** Answered in SR19 and SR20. They're environment variables documented in the README
   and recorded per run in `meta.switches`.

Still open (owner):
- C1–C13: decided 2026-11-20 (see Flagged concerns).
- **Vaatun:** review timing, which decides the hosting tier window (C12), and repo visibility. The repo
  stays private until they answer.
