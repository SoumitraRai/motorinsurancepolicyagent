---
change: 2026-11-20-brokerage-rate-agent
status: accepted
owner: Soumitra Rai (engineer)
author: AI coding assistant
risk: high
tracker: ""
spec_commit: 9aeac7d
---
# Plan: Brokerage rate agent (Vaatun INS/001)

## Context

This plan implements the accepted `spec.md` (`9aeac7d`), built from the accepted `intent.md` (`f8579cd`).
The deliverable is a hosted app: upload a motor policy PDF in the browser; a background worker OCRs it
locally (RapidOCR plus Tesseract); an LLM via OpenRouter (or, as a fallback, local rules) extracts facts
with quotes; code checks the quotes; and
deterministic code resolves the OD and TP brokerage from the original grid files with exact citations.
Runs persist in Supabase. The repo is greenfield apart from the sdlc scaffold. The deadline is
2026-11-21. If time runs short, the PO asks Vaatun for more time (intent).

Decided in the plan interview:
- **Repo:** private on GitHub, with Vaatun invited at submission. The bundle is committed as-is,
  unchanged.
- **Execution:** native, one session. Each task is built failing-test-first (TDD), then one fresh
  reviewer checks the whole branch (`/sdlc:review`).
- **Accounts:** none exist yet (GitHub, OpenRouter, Supabase, Render). Everything before deploy runs
  locally: Postgres in Docker, a mocked OpenRouter transport, the local `rules` extractor, and a local
  object store.
- **Extraction:** the PO amended the spec in the plan interview. There's no Anthropic key, so extraction
  is pluggable: OpenRouter by default, with a local rule-based fallback. Each account is needed only
  at the task marked 🔑. The PO creates it; the assistant never does.

Spec terms used below: SR = requirement, AC = acceptance criterion, C = flagged concern (decided).
Working branch: `sdlc/2026-11-20-brokerage-rate-agent`. Every commit carries
`SDLC-Change: 2026-11-20-brokerage-rate-agent`.

## Global constraints
These apply to every task.

**Architecture**
- Python 3.12 via uv. The backend package is `rater` in `backend/src/rater/`, with tests in
  `backend/tests/`.
- Frontend: Vite + React 18 + TypeScript + Tailwind + shadcn/ui + TanStack Query + `@supabase/supabase-js`,
  in `frontend/`.
- `make build|test|lint|format|run` at the repo root must print `Build succeeded`, then `passed`, then
  `All checks passed` (`sdlc.config.json`).
- The LLM is reached only through `backend/src/rater/extraction/providers/` (amended AC15). The default
  provider is OpenRouter's OpenAI-compatible chat completions API over httpx, with a JSON-schema response
  format and image input. Settings: `EXTRACTION_PROVIDER=openrouter|rules`, `OPENROUTER_API_KEY`,
  `EXTRACTION_MODEL` (a vision-capable model the PO picks from OpenRouter's catalogue at T12; no model id
  is hard-coded). With no key, or on any provider error, timeout or rate limit, the run uses the local
  `rules` extractor, and `meta.extractor` records which extractor ran.
- `insurance-rater-agent-challenge/` is never written to. Grids load only after the MANIFEST check (SR11).

**Grid reading and resolution**
- XLSX values come from `openpyxl.load_workbook(path, data_only=True)` only. Formulas are read separately,
  just to flag a formula cell that has no cached value as `MISSING` (B1, SR12).
- Sheet names are used byte-for-byte.
- Citation strings:
  - `<file> · page N`
  - `<file> · '<sheet>'!<range>`
  - `<file> · page N · table '<name>' · row '<label>'`

  where `<file>` is the path relative to `insurance-rater-agent-challenge/`.
- Resolution (`rater/resolve/*`) is pure: no I/O, no clock, no randomness. Output JSON uses
  `json.dumps(sort_keys=True, ensure_ascii=False)`.
- Switches come from the environment, with these defaults: `GRID_DATE_POLICY=warn`,
  `BROKER_ELIGIBILITY=assume_base`, `LESSER_PERCENT_MEANS=points`.

**Tests**
- No test, fixture or code branch is keyed to a sample's expected rate (NN5).
- Tests may open sample PDFs only in `backend/tests/e2e/`, and only assert structure there.
- `make lint` runs `scripts/check_no_sample_answers.py`. It fails if any file under `backend/tests/`
  (outside `e2e/`) reads `samples/output/` or `sample-policies/`.

**Logging and secrets**
- Logs: the run id, the step name and the duration only. Never fact values, quotes or file contents
  (AC20).
- Secrets come only from the environment. Nothing reads or writes `.env*`.

## Review focus
Inputs the spec implies that are most likely to bite a reviewer. Each is pinned by a test in the task
named.
1. **A PDF that has no extractable facts at all** (blank, or a non-policy document) must end as
   `unsupported` with "no policy facts found", not fail. (T13 `test_pipeline_blank_pdf_unsupported`)
2. **An insurer name in a variant spelling** ("Go Digit General Insurance Ltd.", "DIGIT", "Reliance
   General", "HDFC ERGO General Insurance Company Limited") must select the right grid. An unknown insurer
   returns `unsupported`, naming the four supported ones. (T9 `test_select_insurer_aliases`)
3. **An encrypted or corrupt PDF** must be rejected at upload with a clear message, never crash the
   worker. (T3 `test_upload_rejects_encrypted_and_corrupt`)
4. **The worker dying mid-run.** After a restart, the job must be picked up again (lock timeout) and not
   stay stuck in `processing` forever. (T2 `test_stale_job_lock_is_reclaimed`)
5. **The same PDF uploaded twice** gives two separate runs, both listed. Nothing is deduplicated away.
   (T2 `test_duplicate_upload_creates_two_runs`)

## Files that change
All files are new unless marked (modify). The same pattern repeats for the adapters (one file per sheet
layout) and their tests.

**Root**
- `Makefile`
- `README.md`
- `Dockerfile`
- `render.yaml`
- `.dockerignore`
- `scripts/check_no_sample_answers.py`
- `migrations/001_init.sql`
- `samples/output/{pvt-car-comprehensive-hdfc-ergo,pvt-car-satp-go-digit,pvt-car-comprehensive-reliance,pvt-car-satp-tata-aig}.{json,md}`
- `.gitignore` (modify: add `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`)
- `.github/workflows/sdlc-{deploy,control-band,mention,spec-on-intent}.yml` (modify: triggers →
  `workflow_dispatch` only, before the first push)
- `sdlc/changes/2026-11-20-brokerage-rate-agent/plan.md` (this plan) and `.sdlc/current`

**Backend**: `backend/pyproject.toml`, `backend/uv.lock`, and under `backend/src/rater/`:
- `__init__.py`, `config.py`, `switches.py`, `bundle.py`, `citations.py`, `facts.py`, `result.py`,
  `pipeline.py`, `cli.py`, `worker.py`
- `grids/`: `model.py`, `xlsx.py`, `pdfgrid.py`, `bands.py`, `textrules.py`, `registry.py`
- `grids/adapters/`: `hdfc_pvtcar_pdf.py`, `godigit_4w.py`, `godigit_tw.py`, `godigit_cv.py`,
  `godigit_bus.py`, `reliance_pvtcar.py`, `reliance_feb_grid.py`, `reliance_tw.py`, `tata_pvtcar.py`,
  `tata_cv_tw.py`
- `resolve/`: `select.py`, `mapping.py`, `match.py`, `exceptions.py`, `dates.py`, `confidence.py`,
  `engine.py`
- `extraction/`: `render.py`, `ocr.py`, `verify.py`, `normalise.py`, `schema.py`
- `extraction/providers/`: `base.py`, `openrouter.py`, `rules.py`
- `storage/`: `base.py`, `postgres.py`, `objects.py`
- `api/`: `app.py`, `auth.py`, `routes.py`, `models.py`

**Backend tests**: `backend/tests/` mirrors the source tree (`test_<module>.py`), plus `conftest.py`
(a Postgres fixture via Docker `postgres:16`, synthetic grids, and a mocked OpenRouter transport) and
`e2e/test_samples.py`.

**Frontend**: `frontend/{package.json,vite.config.ts,tsconfig.json,index.html,tailwind.config.ts}`, and
under `frontend/src/`:
- `main.tsx`, `api.ts`, `auth.ts`
- `pages/{SignIn,History,RunPage}.tsx`
- `components/{StatusBadge,RatesCard,TraceList,FactsTable,UploadDrop,ClarifyPanel}.tsx`
- `*.test.tsx` next to each page and component

## Order of work
Tasks marked ∥ in the same phase touch different files and could run in parallel. Execution is native
and sequential, as chosen. Every task ends with `make test` and `make lint`, which must show `passed`
and `All checks passed`. Then a commit `feat(<area>): …` with the trailer.

### Phase A: baseline gate (SR1–SR3, R6)

**T1. Skeleton and tooling**
- Root `Makefile` targets:
  - `build`: `uv sync`, `npm ci`, `npm run build`, then echo `Build succeeded`.
  - `test`: `uv run pytest -q`, then `npm test -- --run`. Pytest prints `N passed`.
  - `lint`: `ruff check`, `ruff format --check`, `mypy src`, `eslint`, the sample-answer check, then
    echo `All checks passed`.
  - `format`
  - `run`: `uvicorn rater.api.app:app` plus the worker.
- Add `scripts/check_no_sample_answers.py`.
- Change the four auto-workflows' triggers to `workflow_dispatch` only.
- **Test:** `test_smoke.py::test_package_imports`.
- **Proof:** all three make targets print their healthy markers.

**T2. Storage** (SR3, SR24; AC16, AC17)
- `migrations/001_init.sql` creates tables `runs`, `jobs`, `pages` and `audit_events`, with the columns
  in spec Design › Storage, plus RLS on `user_id`.
- `storage/base.py`:
  - `RunStore` protocol: `create_run(user_id, file_name, pdf_sha256, storage_key, page_count) -> RunRow`;
    `get_run(user_id, run_id) -> RunRow | None`; `list_runs(user_id, cursor, limit) -> Page[RunRow]`;
    `set_result(run_id, status, result_json, versions, switches)`; `set_failed(run_id, error)`.
  - `JobQueue` protocol: `enqueue(run_id)`; `claim(lock_timeout_s=600) -> Job | None`, implemented with
    `FOR UPDATE SKIP LOCKED` and reclaiming stale locks; `complete(job_id)`; `fail(job_id, err)`.
- `storage/postgres.py`: psycopg 3 implementation.
- `storage/objects.py`: `ObjectStore` protocol `put(key, bytes)`, `get(key) -> bytes`,
  `signed_url(key, ttl_s=300) -> str`, with `SupabaseObjectStore` (httpx to the Storage REST API) and
  `LocalObjectStore(root)`.
- **Tests:**
  - `test_run_roundtrip_after_reconnect` (new connection, identical row; PDF SHA-256 equal)
  - `test_other_user_cannot_read_run`
  - `test_stale_job_lock_is_reclaimed`
  - `test_duplicate_upload_creates_two_runs`
  - `test_signed_url_expires` (local store issues an HMAC URL with expiry, verified at access)

**T3. API, auth and worker** (SR1, SR2, SR25 endpoint; AC18, AC19, AC20)
- `api/auth.py` `verify_jwt(token) -> Principal` checks against Supabase JWKS
  (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, cached). Tests sign tokens with a local RSA key served
  as a fake JWKS.
- `api/routes.py` implements the six routes in spec Design › API:
  - Pydantic models in `api/models.py` with `extra="forbid"`.
  - Upload checks: `%PDF-` magic bytes, ≤ 25 MB, ≤ 60 pages, not encrypted (pypdfium2 open).
  - Rate limit of 10 per minute per user, held in memory per process (this is a documented limitation).
  - An audit event for every state change.
- `worker.py` `run_forever(store, queue, objects, pipeline)` claims a job, calls
  `pipeline(pdf_bytes, file_name) -> Result`, then stores the result. Until T13, the pipeline is the
  `NotReadyPipeline`, which returns `unsupported` with reason "analysis engine not deployed". It isn't
  shipped past T13.
- **Tests:**
  - `test_all_routes_require_jwt_except_health` (iterates `app.routes`)
  - `test_upload_limits` (26 MB, 61 pages, a non-PDF → 413/422 with a message)
  - `test_upload_rejects_encrypted_and_corrupt`
  - `test_upload_then_worker_completes` (a fake pipeline is fine)
  - `test_logs_contain_no_fact_values` (capturing handler)

**T4. Frontend** (spec UX)
- Sign-in uses supabase-js email/password, with sign-ups disabled server-side.
- History, Upload and RunPage implement the states in spec UX: empty, loading skeleton after 300 ms,
  processing with 3 s polling, failed with retry, and done.
- `StatusBadge` shows text plus colour. Status changes are announced with `aria-live="polite"`.
- **Tests (vitest + testing-library):**
  - `History.test.tsx`: empty state copy; rows render; status text present
  - `RunPage.test.tsx`: processing state polls; done renders rates, trace and facts; SATP shows "Not
    applicable" for OD
  - `UploadDrop.test.tsx`: rejects non-PDF and >25 MB inline
- FastAPI serves `frontend/dist` at `/`.

**T5. 🔑 Deploy** (needs GitHub, Supabase, Render)
- `Dockerfile`: python:3.12-slim with `tesseract-ocr` and `tesseract-ocr-eng`; the RapidOCR models
  downloaded at build time; the frontend built in a node stage.
- `render.yaml` defines a `web` service (uvicorn) and a `worker` (`python -m rater.worker`). The
  environment holds `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DATABASE_URL`, `OPENROUTER_API_KEY`,
  `EXTRACTION_PROVIDER`, `EXTRACTION_MODEL` and the switches.
- The PO creates the Supabase project: runs `001_init.sql`, creates the private bucket `policies`,
  disables sign-ups, and creates the reviewer user.
- **Proof (manual, AC22 first pass):** upload a PDF on the hosted URL. It's still listed after refresh,
  reopen, sign-out/in, a Render manual restart, and a redeploy. Timestamps are recorded in the README.

### Phase B: engine (SR4–SR24), for the four sample paths first

**T6. Bundle and citations** (SR11; AC1, AC3)
- `bundle.py` `verify_bundle(root: Path) -> BundleInfo` returns the files and the manifest SHA-256. It
  raises `BundleIntegrityError(path, expected, actual)`.
- `citations.py`: frozen dataclasses `PolicyCite(file, page)`, `XlsxCite(file, sheet, range)` and
  `PdfGridCite(file, page, table, row)`, each with `.render() -> str` in the formats above.
- **Tests:**
  - `test_manifest_all_files_ok`
  - `test_tampered_copy_fails` (copies the bundle to a tmp dir, flips one byte)
  - `test_render_preserves_sheet_spaces` (`'4W  RTO'`, `'School & Staff Bus '`)

**T7. Grid core** (SR12, SR13, SR18; AC4, plus bands for C6)
- `grids/model.py`: `Band(lo, hi, lo_incl, hi_incl, unit)` with `.contains(x) -> bool`; `RateRule`,
  `MappingTable`, `ExceptionRule`, `Grid` and `GridSet`, matching the spec's common rule model. Every rule
  holds a `cite` and a `raw` value.
- `grids/xlsx.py` `SheetView(path, sheet)`: `.value(coord)` returns the cached value, or `MISSING` for a
  formula with no cache; `.is_error(coord)`; `.rows()`.
- `grids/pdfgrid.py` `read_pdf_tables(path) -> list[PdfTable]` uses pdfplumber words grouped by y, with
  columns from header x-ranges. A `PdfTable` has `page`, `name` and `rows`, where each row has `label`
  and `cells[col_path]`.
- `grids/bands.py` `parse_band(label, unit) -> Band | None`. Test cases cover every label form found:
  `<1000`, `>1000`, `1000-1500`, `>1500`, `<10k`, `>10-50k`, `>50k-1L`, `>1L-2L`, `>2L`, `<10`, `>10`,
  `All`, `Upto 5years`, `Above 5 Years`, `0-5 years`.
- `grids/textrules.py` `classify(text: str) -> ExceptionRule`. Kinds:
  - `broker_side`: volume, lakh/lac/crs per month or year, GWP, synergy, "partner", enabler/deal-based.
  - `policy_condition`: "<1000 CC … X% lesser", "X% … reduced", "if sourced … X% additional", "Flat X%",
    "declined", "is to be considered in Petrol Grid".
  - `out_of_scope`: product keywords outside the rule's product, e.g. EW, School Bus, GCV for a private
    car.
  - `unclassified` otherwise.
- **Tests:**
  - `test_missing_cache_is_missing` (the real `School & Staff Bus ` sheet has 7 such cells)
  - `test_ref_and_subtotal_not_data`
  - `test_band_gap_values` (1000, 10, 10000 are contained by none of the adjacent bands)
  - `test_classify_examples`: a table of the real T&C lines with their expected kind. The expected kind
    is a classification, not a rate, so this is allowed.
  - `test_pdf_table_rows_have_labels`

**T8. Result, facts, switches and confidence** (SR21–SR23)
- `facts.py`: Pydantic `Fact[T]` with `value | None`, `raw`, `page`, `quote`, `verification`,
  `confidence`; `Facts` with the SR5 fields; and enums `Fuel`, `PolicyType`, `BusinessType` and
  `VehicleClass`. `VehicleClass` values: `private_car`, `two_wheeler`, `scooter`, `gcv`, `pcv_taxi`,
  `pcv_3w`, `school_bus`, `staff_bus`, `misc_d`, `tractor`.
- `result.py`: Pydantic `Result` matching the spec's JSON exactly, with `to_json()`.
- `switches.py`: `Switches.from_env()`.
- `resolve/confidence.py`: `fact_level(f)`; and `overall(used_facts, warnings, caps) -> Confidence`,
  which applies the weakest link, one level down per D1 warning, and the C1 cap.
- **Tests:**
  - `test_example_keys_preserved` (the challenge example's keys are a subset)
  - `test_satp_od_shape`
  - `test_confidence_weakest_link`
  - `test_d1_warning_lowers_one_level`
  - `test_text_layer_high_ocr_medium_one_engine_low`

**T9. Resolver** (SR15–SR20, SR22; AC5–AC11). Pure functions, tested against a synthetic `GridSet`
built in `conftest.py`.
- `select.py` `select_grids(facts, gridset) -> Selection | Refusal`, including the insurer alias table.
- `mapping.py` `map_facts(facts, grid) -> list[MappingStep] | Refusal`.
- `match.py` `match(facts, mapped, grid) -> list[RateRule] | Refusal`.
- `exceptions.py` `apply(rules, facts, grid, switches) -> Applied`.
- `dates.py` `check_dates(facts, grid, switches) -> list[Warning] | Refusal`.
- `engine.py` `resolve(facts: Facts, gridset: GridSet, switches: Switches, policy_file: str) -> Result`.
- **Tests:**
  - `test_all_dims_match_resolved`
  - `test_no_row_unsupported`
  - `test_two_rows_differ_ambiguous_cites_both`
  - `test_unknown_needed_fact_ambiguous`
  - `test_band_gap_ambiguous`
  - `test_missing_mapping_unsupported`
  - `test_satp_od_never_zero` (property test over insurers)
  - `test_published_zero_tp_reported`
  - `test_package_no_tp_rate_c3`
  - `test_footnote_overrides_cell`
  - `test_broker_side_not_applied_listed`
  - `test_unclassified_tc_ambiguous`
  - `test_d1_warn_and_strict`
  - `test_d2_switch`
  - `test_c2_points_vs_relative`
  - `test_business_type_rules`
  - `test_resolve_deterministic_bytes`
  - `test_select_insurer_aliases`
  - `test_undefined_decline_note_ambiguous_c5`
  - `test_max_cd2_labelled_c7`
  - `test_grid_mapping_beats_printed_location`

**T10. Adapters, wave 1** (SR13, SR14, SR16; AC2). The four files are ∥ with each other.
- `hdfc_pvtcar_pdf.py`: Zone 1/Zone 2 tables from page 1, the state→zone table, footnotes, and the C1 slab
  footnote as a confidence cap.
- `godigit_4w.py`: `4W SATP` (fraction values → percent; column F notes → `ExceptionRule`), `4W New
  Business 1+3`, and `4W  RTO` (column C 4WTP, D package, E SAOD).
- `reliance_pvtcar.py`: `PRIVATE CAR COMP, SAOD & STP` (rows A3:F17 plus the T&C column H), `RTO List`,
  `Make Model wise segment`, and `Enabler, PO Guidelines & T&C`.
- `tata_pvtcar.py`: `Pvtcar` (rows 6–565; columns M–BO are clusters named in row 5; dimensions G–L; the
  `#REF!` row 3 and the SUBTOTAL row 567 skipped), plus `General Guidelines` (C7 → TP on net premium,
  C10 → cluster from the policy's RTO location; no model→segment table, which gives C8).
- `registry.py` `load_all(root) -> GridSet`.
- **Tests:**
  - `test_every_rule_citation_reads_back`: property test over all loaded rules. Re-open the cited cell or
    PDF row and assert it equals `rule.raw`.
  - `test_rule_counts_match_sheet_rows`: the count is computed from the sheet itself, e.g. the number of
    non-empty rows with a cluster in column B.
  - `test_tata_has_no_segment_mapping`

**T11. OCR, verification and normalisation** (SR4, SR6–SR10; AC12–AC14)
- `render.py` `render_pages(pdf: bytes, dpi=300) -> list[PIL.Image]`, plus `text_layer(pdf) ->
  list[str]` (pypdfium2).
- `ocr.py`: an `OcrEngine` protocol; `RapidOcrEngine` rebuilds rows by y-overlap, then sorts by x;
  `TesseractEngine` uses `--psm 6`; `ocr_document(...) -> list[PageText]`, running pages in parallel with
  `ProcessPoolExecutor(max_workers=os.cpu_count())`.
- `verify.py` `verify_quote(quote, page_texts: dict[str, str]) -> Verification`, comparing whitespace-
  and case-stripped text.
- `normalise.py` `normalise(raw: RawExtraction, pages) -> Facts`. Covers the RTO regex
  `^([A-Z]{2})[- ]?(\d{1,2})`, the fuel synonyms table, CC as an integer, ₹ amounts as decimals, `%` next
  to ₹ never taken as a rate, ISO dates, `0001-01-01` as unknown, business type (SR8), policy type from
  the title and premium sections only (SR9), and NCB selection (SR10).
- **Tests** (synthetic images rendered with PIL, and synthetic text; no sample answers):
  - `test_rapid_rows_rebuilt_label_value_same_row`
  - `test_verify_both_one_none`
  - `test_placeholder_date_unknown`
  - `test_rto_normalised`
  - `test_percent_beside_rupee_not_rate`
  - `test_watermark_ignored_for_policy_type`
  - `test_two_ncb_figures_applied_one_wins`

**T12. Extraction providers: OpenRouter plus local rules** (amended SR5; amended AC15) ∥ T11
- `schema.py` holds the JSON schema: per SR5 field, `{value: string|null, page: int|null, quote:
  string|null}`, with `additionalProperties: false`.
- `providers/base.py`: an `Extractor` protocol with `name: str` and `extract(pages: list[PageInput]) ->
  RawExtraction`, plus `choose_extractor(settings) -> Extractor` and `extract_with_fallback(pages,
  primary, fallback) -> tuple[RawExtraction, str]`. The second value is the name of the extractor that
  ran. The fallback runs on any primary exception or schema violation.
- `providers/openrouter.py`: `OpenRouterExtractor(api_key, model, timeout_s=120)` POSTs to
  `https://openrouter.ai/api/v1/chat/completions` with httpx.
  - The request sends `response_format: {type: "json_schema", json_schema: {name: "policy_facts",
    strict: true, schema}}` and the page images as base64 PNG `image_url` parts plus page-tagged OCR text.
  - The prompt says to copy quotes verbatim from the OCR text, to return null rather than guess, and
    never to compute rates or choose grids.
  - The response is validated against the schema. A non-2xx status, a timeout, or invalid JSON raises
    `ExtractionError`.
  - Before writing the code, check OpenRouter's current API docs for `response_format` and image input,
    and record what was checked in Departures.
- `providers/rules.py` `RulesExtractor`: label → value matching over the rebuilt OCR rows. Labels come
  from a synonyms table, e.g. "Registration No", "Vehicle Registration No.", "RTO Location", "Cubic
  Capacity", "CC / HP", "Fuel Type", "Year of Manufacture", "Mfg. Year", "Year of Mfg.", "Make",
  "Model", "Period of Insurance", "Issuance Date", "Policy Issue Date", "Basic Own Damage", "Basic Third
  Party Liability", "No Claim Bonus", "Previous Policy … of <insurer>", and the insurer from the IRDAI
  footer or header line.
  - Each match returns the row text as the quote and its page.
  - The table holds generic insurance labels only, never sample values.
- **Tests:**
  - `test_only_providers_make_llm_calls` (AST scan: no `httpx` or `openai` import outside
    `providers/`, `storage/` and `api/`; no `providers` import from `grids/` or `resolve/`)
  - `test_openrouter_request_shape` (`httpx.MockTransport`: schema and image parts present)
  - `test_openrouter_response_parsed`
  - `test_openrouter_error_falls_back_to_rules` (500, timeout, 429 and invalid JSON each give
    `extractor == "rules"`)
  - `test_rules_extracts_from_synthetic_rows` (synthetic rows only)
  - `test_rules_unknown_label_gives_null`
- **Spec amendment, in the same commit as this task's first test:** edit spec.md SR5, the extraction
  call, Approaches 2, AC15 and the example `meta.model` → `meta.extractor`/`meta.model`. Add a line
  "Amended 2026-11-20 by PO: OpenRouter + local fallback (no Anthropic key)", keeping
  `status: accepted`. The PO decided this in the plan interview.

**T13. 🔑 Pipeline, CLI and sample outputs** (SR24, SR26; AC21; needs an OpenRouter key with credits for
the real-model outputs; without one, the outputs are generated with `rules` and labelled so)
- `pipeline.py` `run_pipeline(pdf: bytes, file_name: str, deps: Deps, overrides: dict[str, str] | None =
  None) -> Result` wires T11, T12 and T9, and records `meta`. It replaces `NotReadyPipeline` in the worker.
  `overrides` holds the reviewer-supplied facts from `/clarify` (SR25). Each one is marked
  `verification: "reviewer_supplied"`, and the run's `parent_run_id` is set.
- Extra test: `test_clarify_override_marked_and_linked`.
- `cli.py` `python -m rater.cli run <pdf> --out samples/output/<stem>` writes `.json` plus the readable
  `.md` trace.
- **Tests:**
  - `test_pipeline_blank_pdf_unsupported` (fake LLM)
  - `e2e/test_samples.py::test_sample_structure`, run with the `rules` extractor always, and also with
    OpenRouter when `OPENROUTER_API_KEY` is set. It checks a schema-valid result, every `gridCitation` re-reading via T10's checker, and SATP samples having
    `od.applicable is False`. It never checks a rate.
- Generate the 4 outputs with the CLI and commit them unedited.
- Redeploy, then re-run the AC22 checklist.

### Phase C: the rest of A1 (SR14), then documentation

**T14. Adapters, wave 2: two-wheelers.** The files are ∥ with each other.
- `godigit_tw.py` (`TW 1+1 & SATP`, `TW 1+5`, `2W Grid 5+5`, `TW SAOD with Flexi Options`, `2W RTO's`)
- `reliance_tw.py` (`TW SCOOTER GRID`)
- `tata_cv_tw.py` (`TW` part)

**T15. Adapters, wave 3: CV, taxi, bus and misc.** The files are ∥ with each other.
- `godigit_cv.py` (`CV Grid (excl. HCV)`, `HCV GRID`, `TAXI Segments and Location wise`,
  `CV RTO Mapping`)
- `godigit_bus.py` (`School & Staff Bus `, `School & Staff Bus RTO`)
- `reliance_feb_grid.py` (`FEB'26 - Grid`)
- `tata_cv_tw.py` (`CV` part)

T14 and T15 reuse T7's primitives and extend `registry.py`. **Test:** the same
`test_every_rule_citation_reads_back` property test now covers all sheets. Plus per adapter
`test_<adapter>_loads`, and a synthetic-facts resolve test per vehicle class through the T9 engine.

**T16. README and architecture note** (SR27)
- README sections:
  - setup, run and deploy (Render + Supabase steps);
  - storage and persistence per R6 event;
  - the A/B/D and C1–C13 decisions as assumptions;
  - the switches;
  - that uploads go to OpenRouter and the upstream model provider when a key is set, and stay local
    with the `rules` extractor otherwise;
  - links to `samples/output/*`;
  - architecture, failure modes and trade-offs;
  - the AC22/AC23 manual evidence.
- Then `/sdlc:verify` and `/sdlc:review`.

## Risks
- **Riskiest step: T10/T15 adapter mis-parses**, such as an off-by-one row or a shifted column on the
  70-column `Pvtcar` sheet. That would give a confident wrong rate, which costs the most score (40%
  accuracy).
  - Made safe by the read-back property test: every rule's cited cell must hold that rule's raw value.
  - Rule counts are derived from the sheet itself.
  - Unknown layouts fail loudly at load time, never silently.
- **Deploy (T5) is blocked on accounts.**
  - Mitigation: Phase B doesn't need T5 and continues locally. Every 🔑 task names exactly what the PO
    must create.
  - Free tiers sleep or pause (C12). Upgrade before submission.
- **The exception classifier marks too much `unclassified`**, so too many results are `ambiguous`.
  - Mitigation: `test_classify_examples` lists every real T&C line in an in-scope sheet with its kind, so
    the inventory is reviewed once.
  - `unclassified` lines are visible in the trace.
- **OCR or the extractor misses a fact on unseen policies.** The fact becomes `unknown` or `low`, and the
  result `ambiguous`, never a wrong rate, by design. The `e2e` structure test catches regressions.
- **OpenRouter is unavailable, rate-limited, or the key runs out of credit during review.** The run falls
  back to `rules`, so the baseline gate still holds, but accuracy drops on layouts the rules don't know.
  The PO should fund the key for the review window, and the trace shows which extractor ran.
- **A model's JSON-schema support varies on OpenRouter.** Schema validation plus fallback means a model
  that ignores the schema degrades to `rules` rather than crashing. Pick the model at T12 by running the
  e2e structure test.
- **Docker image size and build time** (onnxruntime, models, tesseract). Use a multi-stage build and
  download the models at build time. Rough target ≤ 1.5 GB.
- **Time (C9).** Phases A and B secure the baseline gate and the four samples. If Phase C slips, the PO
  asks Vaatun for more time. Nothing is cut silently.
- **Pushing triggers the auto-workflows.** T1 switches them to manual before any push.

## Options not taken
- **Subagent per task, or parallel worktrees.** Chosen: native, for deadline speed. ∥ marks stay for
  later use.
- **Public repo without the bundle.** The PO chose private. Revisit if Vaatun says otherwise.
- **Celery/Redis queue.** A Postgres `SKIP LOCKED` queue is enough and keeps one fewer service awake.
- **Generic grid inference, or an LLM normalising the grids.** Rejected in the spec. Neither is
  deterministic enough, and the LLM option breaks NN1.
- **Anthropic SDK** (the original spec choice). There is no key, so the PO chose
  OpenRouter plus a local fallback. An Anthropic provider can be added behind the same `Extractor` interface
  later.
- **A separate static host for the frontend.** FastAPI serves `frontend/dist`, giving one deploy unit.

## Proof
"Done" means all of the following, with fresh output pasted at `/sdlc:verify`:
1. `make build`, then `Build succeeded`; `make lint`, then `All checks passed`; `make test` showing
   `passed` with 0 failed and 0 skipped. The exception is `e2e`, whose OpenRouter leg is skipped only when no
   `OPENROUTER_API_KEY` is set, and must run with a key before submission.
2. Every AC1–AC21 maps to a named test above. AC22 and AC23 are manual, with evidence and timestamps in
   the README.
3. `samples/output/` holds 4 JSON plus 4 `.md` files generated by the CLI. Each is schema-valid, and
   every citation re-reads.
4. The hosted URL accepts an unseen PDF, and the run survives refresh, reopen, sign-out/in, restart and
   redeploy (the baseline gate).
5. The `/sdlc:review` findings are resolved, or explicitly accepted by the PO.

## Departures from plan
<!-- Filled in during build. Each entry: what changed vs. the plan above, why, commit. -->

- **T1: minimal frontend scaffold created in T1, not T4.** `make build/test/lint` run both halves, so
  T1 needed a building and testing frontend. Added `frontend/{package.json, package-lock.json, tsconfig.json,
  vite.config.ts, index.html, eslint.config.js, tailwind.config.ts, postcss.config.js}`,
  `src/{App.tsx, App.test.tsx, main.tsx, index.css, test-setup.ts, vite-env.d.ts}`. T4 builds the pages on
  top. (T1 commit)
- **T1: `make format` accepts file arguments.** The sdlc `format-on-edit` hook runs `make format "<file>"`.
  The Makefile formats only the named files when given, and everything otherwise. (T1 commit)
- **T1: the guard script exempts its own test.** `backend/tests/test_check_no_sample_answers.py` must contain
  the forbidden strings to test the guard, so `scripts/check_no_sample_answers.py` skips that one file by
  name. (T1 commit)
- **T1: `sdlc-deploy.yml` lost its `workflow_dispatch` inputs** when its triggers were switched to manual
  only. Restoring them from the shell was blocked by the `production-gate` hook: the command text named the
  release environment, though nothing was deployed. The PO chose option 1: the inputs were restored with a file
  edit (Edit tool). Only push and schedule triggers are removed. (T1 commit)
- **T2: `migrations/001_init.sql` is a protected path** (`**/migrations/**`: tech lead plus a change
  ticket). The agent's write was blocked by the `protected-paths` hook. On 2026-11-20 Soumitra Rai, acting as
  platform engineer and TL, removed the `**/migrations/**` entry from `sdlc.config.json` `protectedPaths`.
  The PO ran the edit themselves, since `sdlc.config.json` stays protected. Migrations are no longer gated by
  the hook. Change reference: plan T2. Also: RLS is created only where Supabase's `auth` schema exists, so the
  same file runs on plain Postgres in tests. (T2 commit)
- **T2: storage additions beyond the plan's interface.** `RunStore.get_run_any_user` (the worker reads a run
  without a user context), `PostgresStore.set_queued` (for retry), `RunStore.audit`, and
  `LocalObjectStore.verify` (the local signed-URL check served by the API's `/api/files` route). Also, `Page`
  carries `next_cursor` for keyset pagination. (T2 commit)
- **T3: API and worker departures.**
  - `migrations/002_run_overrides.sql` adds `runs.overrides`, which holds the reviewer-supplied facts for
    clarification reruns (SR25).
  - The worker's pipeline returns `PipelineOutput(status, result_json, versions, switches)` until the
    `Result` model lands (T8/T13).
  - The uvicorn entry point is the factory `rater.api.app:create_app_from_env`.
  - The object key is `{uuid}/{sha256}.pdf` (the object is stored before the run row exists).
  - `/api/files/{key}` serves local-store signed URLs and requires the JWT, so the frontend fetches PDFs
    with the auth header.
  - `/health` doesn't yet check the grid manifest or the DB (added in T6).
  - The route test enumerates the router directly, because FastAPI 0.165 nests included routers.
  - A Starlette TestClient deprecation warning remains (one warning in test output). It was cleared in
    T4 by adding the `httpx2` dev dependency.
  - (T3 commit)
- **T4: frontend departures.**
  - Components are hand-written Tailwind, not generated by the shadcn/ui CLI (interactive, no gain for
    6 components). They follow the same accessibility rules: text and colour on statuses, `aria-live`
    status, visible labels, 44 px targets.
  - Added files beyond the plan's list: `src/components/rates.ts` (shared rate text), `src/testing.tsx`
    (test helper with a fake `Api`), and `src/pages/SignIn.test.tsx` and `src/App.test.tsx` (sign-in
    form, signed-out and signed-in shells).
  - `App` takes an injected `Auth` (Supabase in the browser, a fake in tests). Supabase's public URL and
    anon key come from `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` at build time.
  - Hash routes (`#/`, `#/runs/<id>`), so FastAPI's static mount needs no open catch-all route.
  - PDFs from the local store are fetched with the auth header and opened as a blob URL.
  - (T4 commit)
- **T5 (partial, no accounts yet): deploy files prepared ahead of the accounts.**
  - `Dockerfile`, `.dockerignore` and `render.yaml` were written and the image built locally: 1.28 GB,
    Tesseract 5.5.0, RapidOCR/OpenCV/pdfium import cleanly, 11 bundle files, SPA present.
  - RapidOCR's ONNX models ship inside the `rapidocr-onnxruntime` wheel, so there's no build-time model
    download.
  - `render.yaml` uses plan `starter` for web and `standard` (2 GB) for the worker, per the memory
    measurement (≈1 GB peak per OCR'd page), with `OCR_WORKERS=1`. `autoDeploy: false`.
  - A local two-container HTTP smoke test was not run: the shell command was denied, since project
    settings deny `curl`. The API is covered by T3's TestClient tests.
  - Remaining for T5 (🔑): GitHub repo, Supabase project (migrations, private bucket `policies`, sign-ups
    off, reviewer user), Render services, then the AC22 checklist.
  - (T5-prep commit)
- **T7: grid core departures.**
  - `grids/model.py` moved to T9, where the resolver's tests define and exercise the rule model. `Band`
    lives in `grids/bands.py`.
  - `xlsx.py` exposes `Workbook(path).sheet(name)` with `.value/.formula/.is_error/.is_aggregate/.cells()`
    instead of a `SheetView(path, sheet)` constructor, so one workbook load serves many sheets.
  - `pdfgrid.py` returns positioned lines (`pdf_lines`) rather than finished `PdfTable`s. The HDFC ERGO
    layout is specific enough that the adapter (T10) builds its tables from x-positions.
  - `textrules.classify` gained three kinds the real lines needed: `undefined_decline` (C5),
    `slab_basis` (C1) and `definition`.
  - (T7 commit)
- **T9: resolver departures.**
  - `grids/model.py` (from T7) and `resolve/common.py` (`Refusal`, `Step`) were added.
  - `select_grid` returns one `Selection` (the single applicable grid) rather than a list. More than one
    applicable grid is a refusal (`ambiguous`).
  - Exceptions carry an explicit `when` condition plus the components they touch, so a footnote that
    names only OD (e.g. "payout on OD premium") never alters TP.
  - Extra tests beyond the plan's list:
    - an identical rate from two rows is not a contradiction;
    - SAOD makes TP not applicable;
    - an unknown vehicle class or policy type is ambiguous;
    - no grid for the vehicle class is unsupported;
    - a two-valued mapping is ambiguous;
    - a past stated end date is unsupported even in `warn` mode;
    - decline footnotes are unsupported;
    - an exception needing an unknown fact is ambiguous;
    - definition/basis/out-of-scope notes never block.
  - (T9 commit)
- **T10: adapters wave 1 departures (HDFC ERGO PDF, Go Digit 4W, Reliance private car, Tata AIG `Pvtcar`).**
  - **PO decision 2026-11-21: a documented country-wide city → state list** (`grids/geo.py`
    `CITY_STATE`) plus the RTO state-code table (`STATE_CODES`) cover every Indian RTO. They are used where
    a grid names regions by state or city (HDFC ERGO state → zone; Reliance region names). A result that
    rests on either is confidence-capped at medium and says so in the trace. README assumption.
  - Model extensions, each with synthetic tests in `tests/resolve/test_engine_extensions.py`:
    - `NotIn` dimension (Go Digit "Others" makes);
    - `MappingTable.if_missing`/`missing_reason` (Tata AIG segment → `unsupported`, C8);
    - `CitySplitTable` (HDFC ERGO states split by city);
    - `RtoRegionTable` with state-code fallback;
    - `MappingRow.note`/`cap`;
    - list-valued facts match any keyword.
  - New facts: `od_term_years` (Go Digit new business 1+3 vs 3+3), `add_ons`, `cpa_cover` (Reliance T&C),
    and the derived dims `has_add_ons` and `ncb_flag`.
  - New `textrules` kinds: `post_issue` (clawbacks after issue) and `process` (insurer internal
    procedure). Both are trace notes only. "CV" counts as a commercial-vehicle word.
  - `grids/makes.py` canonical make aliases ("Volks", "Citrone", "MARUTI SUZUKI").
  - `grids/readback.py` is the shared citation checker (AC2), reused by the e2e test (AC21).
  - Interpretations (README assumptions):
    - Go Digit `All_India_Decline` rows → decline exceptions.
    - Go Digit "A/B" clusters expand to both.
    - Go Digit new-business CD2 applied to OD (basis not stated; confidence capped at medium).
    - Tata AIG "Other Than Diesel" = petrol/LPG/hybrid (CNG and Electric have their own rows).
    - Tata AIG row-4 DM/HOM flags are not used (meaning not stated).
    - The Reliance `RTO List` zone must agree with the rate row's zone, otherwise `ambiguous`.
  - Resulting coverage gaps:
    - Reliance regions Chandigarh, Dehradun/Uttarakhand, Ladakh and Pondicherry fall in no rate row
      (`unsupported`).
    - Jaipur is the one zone conflict (`ambiguous`).
  - Tata AIG tests take ~48 s because openpyxl loads the large hidden `checks` sheets. Accepted for now.
  - Insurer aliases moved to `rater/insurers.py`, so extraction can tell "same insurer" without importing
    adapters.
  - (T10 commit)
- **T11: OCR, verification and normalisation departures.**
  - Pages are OCR'd one at a time by default (`OCR_WORKERS=1`), not in a `ProcessPoolExecutor` sized to
    `os.cpu_count()`. The measured peak is ≈1 GB per page with both engines, and the worker has 2 GB.
    Images are rendered one page at a time (`iter_pages`).
  - Pages with a text layer of ≥ 40 characters skip OCR and verify against that layer (`text_layer`
    verification → high confidence).
  - Extractor output is `RawField(value, page, quote)` per camelCase field. Normalisation also reads
    `registrationNumber` into the RTO code when no explicit RTO code is given.
  - Business type for unknown insurers compares the non-generic words of the two names (e.g. "Acme" vs
    "ACME GENERAL INSURANCE CO").
  - Extra tests beyond the plan's list:
    - Tesseract reads the same rows;
    - an image-only PDF gets both engines;
    - money and date formats;
    - vehicle class, fuel, make and cc;
    - add-ons and CPA;
    - page citation and a failed quote check give low confidence.
  - (T11 commit)
- **T12: providers departures.**
  - Checked OpenRouter's docs on 2026-11-21 (structured outputs, images, chat-completion reference, models
    API): `response_format.json_schema` with `name`/`strict`/`schema`, `provider.require_parameters: true`,
    `image_url` parts with base64 data URLs, the reply in `choices[0].message.content`, and errors as
    `{error: {code, message}}` (402 out of credits, 429 rate limit).
  - No `temperature` is sent: some current models reject sampling parameters, which would silently force
    the rules fallback.
  - `choose_extractor` uses rules when `OPENROUTER_API_KEY` or `EXTRACTION_MODEL` is unset. A model id
    is never guessed.
  - `extract_with_fallback` returns a third value, the reason the primary wasn't used, for the trace.
  - Spec amended in this commit (SR5 wording, extraction call, Approaches 2, AC15, security egress/secrets,
    C10 wording, `meta.extractor`), keeping `status: accepted`, per the PO's plan-interview decision.
  - (T12 commit)
- **T13: pipeline, CLI and sample-output departures.**
  - The e2e test is marked `e2e` and runs with `make e2e` (new Makefile target), not in `make test`. OCR of
    the 40 sample pages takes ~3–4 minutes. It must pass before submission (Proof 1).
  - Running the real samples exposed resolver and extractor bugs, each fixed with a failing test first:
    - an "All" band required its fact (e.g. age with an unknown manufacture year);
    - exceptions scoped to another cluster, zone or region flooded the trace (now silently out of
      scope);
    - OCR drops spaces ("LiabilityOnlyPolicy", "PrivateCar", "GoDigitGeneral InsuranceLimited"), so
      labels and insurer names now match spacing-insensitively;
    - joined registration numbers ("ZZ07AB1234");
    - labels bleeding into the next value;
    - "From 00:00 Hrs on <date>";
    - a make glued to its model ("RENAULTKWID" → `grids/makes.split_make`);
    - business type only from a labelled field, never free text mentioning "renewal".
  - New resolver rule (`match._irrelevant`). An unknown fact with a closed set of values (fuel, NCB flag,
    add-ons, CPA, business type) does not block a result when the grid's candidate rows cover every value
    and all give the same rate. The trace says so and cites every candidate cell. This is exhaustive
    checking, not inference. If the rates differ or a value is uncovered, the result stays `ambiguous`.
  - A car body style printed on the policy (hatchback, sedan, SUV, MUV) normalises to `private_car`.
  - Pipeline `meta` adds `extractor`, `extractorNote`, `model`, `ocr`, `gridManifest`, `pdfSha256`,
    `pages`, `reviewerSupplied` and `seconds`. `seconds` makes pipeline output non-byte-identical across
    runs. Resolution itself stays deterministic (AC11).
  - README drafted during T13 (setup, deploy, persistence, configuration, privacy). T16 completes it.
  - Sample outputs were generated with the local `rules` extractor (no OpenRouter key yet). They are to be
    regenerated with OpenRouter once the PO has a key.
  - **PO decision 2026-11-22: model → fuel reference list, single-fuel models only**
    (`grids/model_fuels.py`).
    - Used only when the policy prints no fuel.
    - A model sold in one fuel supplies it (`verification: derived`, medium confidence, trace note).
    - Multi-fuel models are listed so they deliberately stay unknown, and so `ambiguous`.
    - A printed fuel always wins.
    - A printed CNG/LPG kit value above 0 blocks a petrol-only reading (new fact `cng_lpg_kit_value`).
    - An "EV"/"Electric" model name means electric.
    - README assumption.
    - **List data supplied by the PO on 2026-11-22.** It is stored as `grids/data/model_fuels.csv`
      (make, model, fuels, years, source), validated on load: known fuels only, one row per make+model.
    - The PO built it externally. Most rows are marked "not web-verified"; single-fuel rows are the ones
      that change results.
    - Matching is "starts with", after stripping a glued make prefix, and the longest name wins. This
      fixes short-name collisions such as "800" inside "ALTO 800".
    - With this list the Renault Kwid is petrol|CNG (Renault's Jan-2025 CNG kit release), so the Reliance
      sample stays `ambiguous` on fuel by design.
  - Also fixed during T13 with failing tests first:
    - "Make/Model&Variant" labels (the model came from a page-7 line);
    - "From00:00Hrs" dates;
    - component rows filtered to the policy's own type, so a package policy's TP is "not published" (C3),
      not "no row matches" from the STP rows.
  - (T13 commit)
- **T14: two-wheeler adapters departures.**
  - New adapters:
    - `godigit_tw.py`: five grids, `TW 1+1` (comprehensive, renewal/rollover), `TW SATP`, `TW 1+5` (new,
      OD term 1), `2W Grid 5+5` (new, OD term 5) and `TW SAOD` (OD term 1–4 via the "Max N year CD2"
      columns), with the `2W RTO's` columns C/D/E.
    - `reliance_tw.py`: `TW SCOOTER GRID`. Motorcycles get only the SA OD column, per its own T&C K5.
    - `tata_cv_tw.py` `load_tw`: Tata AIG `TW`, 70 clusters; "All" splits into an OD and a TP rule.
  - `grids/twsegments.py` parses segment labels into OR-of-AND dimension sets:
    - scooter/motorcycle, CC band, make group, "Others" relative to sibling labels;
    - "Other than RE", model families ("Avenger"), EV kW bands, "EV", "SC/EV" (OR) vs "SC_EV" (AND).
    - Unknown labels or makes raise at load time.
  - Model and engine extensions:
    - `Contains` dimension;
    - `<=`/`>=` bands and a kW unit;
    - `tw_type` derived dimension (scooter/motorcycle/moped) from the new `motorcycle` and `moped` vehicle
      classes ("two wheeler" alone leaves it unknown);
    - `power_kw` fact;
    - optional mapping tables;
    - an engine `_explain` step that turns "no row matches" into a cited decline / no-rate refusal when a
      decline note covers the policy.
  - Interpretations (README assumptions):
    - "Max CD2" is the payout; CD1 columns are not brokerage.
    - Text codes "D" and "MISP" in rate cells give no rate; their meaning isn't stated, so the result is
      refused, quoting the code.
    - A package two-wheeler rate is one rate on a stated basis ("Slab Net 5", "OD plus Add on", or "total
      premium" for Tata AIG). It is reported as OD, with TP unpublished and confidence capped.
    - Go Digit SAOD uses "Max N year CD2" by OD term; the plain "CD2" column is not used (capped).
    - 5+5 "W/O Add on" / "W/O CPA" CD2 reductions become row-scoped policy conditions. "Format error"
      notes are row-scoped `unclassified` → `ambiguous`.
    - Reliance TW T&C are applied to fresh business only (EV flat 25%; Yamaha/Hero −2.5%; Kolhapur,
      Mysore, Mangalore and West Bengal excluding Kolkata flat 20%, matched via the `RTO List` region
      name). The contest/GWP table is broker-side.
  - New classifier rules, each tested on the real lines:
    - contest/GWP lines are broker-side;
    - "posting" / "1/2 basis" payment schedules are process notes;
    - "(-)2.5%" is a reduction;
    - "Grid not applicable for" lines are definitions.
  - Reliance region helpers generalised (`parse_region_row` with two-letter state codes and "&",
    `build_region_table`) and shared by private car and scooter.
  - `tests/grids/test_vehicle_classes.py` runs one synthetic policy per two-wheeler grid through the real
    grids and engine.
  - (T13+T14 commit)
- **T15 (part 1), Go Digit `CV Grid (excl. HCV)` + `CV RTO Mapping`.** Built as `grids/adapters/godigit_cv.py`
  and `grids/cvsegments.py` (segment labels → dims); the rest of T15 is not started.
  - Mapping tables gained `when`: one `CV RTO Mapping` column per vehicle type (GCV3, LCV/MCV/HCV by GVW,
    PCV 2W/3W by fuel, PCV by seats, Misc D). LCV/MCV/HCV use the Motor Vehicles Act weight classes
    (≤7.5 t, ≤12 t, >12 t), as the sheet doesn't define them. Tractors use the Misc D column (capped).
  - "Low CD2 RTOs" rows are placed only where the sheet defines them (`_LOWCD2_n` mapping suffix or an
    "Only for <RTOs>" note); RTO-scoped rows take precedence over the cluster's general rows. "All"/"Others"
    rows exclude what sibling rows name (makes, Oil Tanker). Multi-rate cells (CD1-dependent) and undefined
    scopes are row-scoped `ambiguous`; catch-all rows ("GCV4 excl above") count only when no row matches.
  - Cluster labels that differ from the mapping only in spelling are aliased; `KA 1 Good`/`KA 2 Bad` and
    mapping values like `DELHI-1` are not guessed (→ `unsupported`).
  - Resolver fixes, failing test first: a scoped `unclassified` term only refuses policies in its scope
    (it used to block the whole grid, which also affected the 2W 5+5 notes); "no row" plus an undefined
    term covering the policy is `ambiguous`, not `unsupported`; new dims `ContainsAny`/`NotContainsAny`.
  - Extraction: `bodyType`, `tppdRestricted`; vehicle classes `gcv_3w`, `pcv_2w`, e-rickshaw, Misc D, tractor.
  - (T15 part 1 commit)
- **Vaatun's answers applied (2026-11-22, `vaatun-answers-2026-11-22.md`).**
  - D1 reversed: `GRID_DATE_POLICY` defaults to `strict` (outside the grid's period → `unsupported` with
    the reason). `test_d1_warn_and_strict` now passes `warn` explicitly; `test_switches_defaults_and_validation`
    expects `strict`. An unreadable policy date is held back to the end of the run: it gives `ambiguous`
    only if nothing else makes the policy `unsupported` (Tata AIG sample: C8 still decides).
  - Business type: `engine.resolve` tries new/renewal/rollover when an `ambiguous` result is missing only
    the business type; equal rates → resolved with a trace note (`test_unknown_business_type_*`).
  - Pages: `READ_PAGES` limits OCR and extraction. Default 20, not 6: with 6, the Tata AIG sample lost its
    insurer (page 12) and Reliance its previous insurer (page 13); `meta.pagesRead`/`pageCount` recorded;
    upload page limit raised from 60 to 200 (`test_only_the_first_pages_are_read`, `test_upload_limits`).
  - (Vaatun answers commit)
- **Order change (PO, 2026-11-22): the rest of T15 comes after T5.** Go Digit `HCV GRID`, `TAXI Segments
  and Location wise`, `School & Staff Bus ` (+ RTO), Reliance `FEB'26 - Grid` and Tata AIG `CV` are built
  after the deploy, since Vaatun's answer #2 makes private cars plus a working hosted app the priority.
  Scope (A1) is unchanged. Until then those policies return `unsupported`.
- **Local UI preview (not in the plan).** `npm run preview:local` serves `frontend/preview.html` with a
  fake sign-in and the committed `samples/output/*.json`, so the PO can review the screens before Supabase
  exists. `App` takes an optional `api` prop that only the preview passes. Not part of `vite build`.
- **Frontend visual redesign (PO request, 2026-11-22; not in the plan).** Direction chosen by the PO on the
  Impeccable decision page: "Security-Paper Schedule". `PRODUCT.md` (product record) and
  `.impeccable/surfaces/frontend-src-app-tsx.md` (direction contract) record it.
  - Layout: top bar; a 22rem run-list rail (`History`) beside the run page; `Home` start screen with a
    large drop target; the rail hides on phones while a run is open.
  - Run page: one rate-schedule panel (guilloché band, red run serial, Status | OD | TP | Confidence,
    each rate above its citation; "Why there is no rate" for refusals), then Decision trace / Schedule
    fields / JSON tabs following the ARIA tabs pattern (arrow keys, Home/End, labelled panel).
  - Refused runs show "No rate" instead of "Not published"; the upload hint says 200 pages (the new limit).
  - Hind and JetBrains Mono self-hosted via `@fontsource`; themed focus ring, selection, caret and
    scrollbars; reduced motion respected (the band's one print animation is skipped).
  - Tests: `RunPage.test.tsx` assertions moved to the new structure (region "TP rate" holds "20%", tab
    "Schedule fields"); new tests for keyboard tabs and the refusal reason.
- **T5: hosted on AWS EC2, not Render (PO, 2026-11-23).** Render's plans with enough memory need payment;
  the PO has AWS free-plan credits. `deploy/aws/` holds `compose.yml` (web, worker and Caddy for HTTPS on
  one host), `Caddyfile`, `env.template` (the variable list; the filled-in file lives only on the host at
  `/opt/rater/rater.env`), `bootstrap.sh` and `deploy.sh`. Host: `c7i-flex.large` (4 GB) in `ap-south-1`,
  next to Supabase; the 2 GB free-plan types are too small for both OCR engines (≈1.2 GB peak). Same
  Dockerfile, no code change. `render.yaml` is kept but unused. Release authorised by the PO as release
  manager (`RELEASE_APPROVAL`); there is no staging environment, so no rollback rehearsal precedes it.
- **Progress bar while a run is analysed (PO request, 2026-11-23; not in the plan).** `AnalysisProgress`
  replaces the "Analysing this policy" line on queued/processing runs: a `role="progressbar"` bar of elapsed
  time against an estimate (15 s + 12 s per page read, pages capped at `READ_PAGES` 20), the time left, and
  "Taking longer than estimated" past it. The server reports no progress, so the bar is labelled an estimate
  and stops at 95% until the run finishes. Tests: `AnalysisProgress.test.tsx`; `RunPage.test.tsx` processing
  test now finds the bar.
- **Confidence and speed (PO, 2026-11-23; spec C4 and SR23 amended).** The PO lifted the OCR cap: every
  real policy is scanned, so scanned facts must be able to reach `high`.
  - Rules extractor quotes the matched label and value, not the whole OCR row: one misread character in
    another field on the row no longer fails the quote check (`test_rules_quote_is_the_label_and_value_*`).
  - New verification `confirmed_both`: the quote is in both engines and the value read from the
    cross-check engine's text alone (rules extractor) is the same; names compared loosely
    (`test_same_value_from_each_engine_is_confirmed`, `test_names_are_compared_loosely_across_engines`).
  - `confidence.overall`: share of used facts that are `high`, 90% / 70% thresholds (PO), never below the
    weakest link, `low` when a rate-row fact (mapping, match, T&C) is below `medium`; the engine tracks
    those facts (`row_used`). `test_confidence_weakest_link` replaced by the share and row-fact tests;
    `test_pipeline_resolves_and_records_meta` now expects `confirmed_both` (both fake engines agree).
  - Tesseract reads only the pages the facts came from (`ocr_document(only_pages=…)`,
    `pipeline._cross_check`); measured on 2 vCPUs it was ≈ 40% of OCR time on every page
    (`test_cross_check_engine_reads_only_the_cited_pages`).
  - Frontend: the confidence text leads with the confirmed share; the progress estimate is 30 s + 16 s
    per page, from the 2-vCPU measurement. README has a new Confidence section. Sample outputs regenerated.
- **T15 (part 2), Go Digit `HCV GRID`.** Built as `grids/adapters/godigit_hcv.py`, not in `godigit_cv.py`.
  Its rules and exceptions join the existing `godigit/CV Comp` and `godigit/CV SATP` grids, because the
  resolver picks a grid by vehicle class and policy type alone: a separate grid for goods vehicles over 12 t
  would make every such policy "More than one grid applies".
  - Blocks are read from their own header rows: the body-type columns move between blocks (Port Trailer only
    in the first). Readings are in the module docstring and the README (strict: tankers that are neither oil
    nor gas, North Bengal where a West Bengal cell doesn't name it, NL RTOs, Low-CD2-only mapping codes, and
    the Additional Comments that contradict the Bad GJ rows are all `ambiguous`; Volvo/Scania decline).
  - `Sheet.merged()` (xlsx) finds the "to be referred" text across merged tanker columns;
    `parse_cv_segment` reads `44T+` / `40T+` as (x, ∞) (`test_tonnage_plus_starts_above_the_number`).
  - Cluster aliases added: `Bad GJ` spellings, `KA1`/`KA2` → `(EX BLR)`, `GJ REF` → `GUJARAT REF`.
  - Engine: a gap between bands now names an uninterpretable grid term or a decline covering the policy, as
    "no row" already did. A CD1-ladder row used to read as "falls between the published bands"
    (`test_a_row_with_no_single_rate_is_named_not_reported_as_a_gap`).
  - Tests: `tests/grids/adapters/test_godigit_hcv.py` (17).
- **T15 (part 3), Go Digit taxi and bus sheets.**
  - `grids/adapters/godigit_taxi.py` reads `TAXI Segments and Location wise` into `godigit/CV Comp` and
    `godigit/CV SATP` (same reason as HCV: taxis are `pcv_taxi`, which those grids already cover).
  - `grids/adapters/godigit_bus.py` reads `School & Staff Bus ` and `School & Staff Bus RTO` as a new grid
    `godigit/Bus Comp` (school and staff buses), not in `godigit_cv.py` as the plan's file list had it.
  - The bus rate splits on who runs the bus, which no fact carries. The engine now names such a grid
    dimension in the refusal without treating it as a fact (`Facts.has`); confidence scores facts only.
  - Readings: README. Tests: `test_godigit_taxi.py` (13), `test_godigit_bus.py` (14).
- **T15 (part 4), Reliance `FEB'26 - Grid` and Tata AIG `CV`.** T15 is complete.
  - `grids/adapters/reliance_cv.py`, not `reliance_feb_grid.py` (plan's name): grids `reliance/CV Comp`
    and `reliance/CV SATP`, mapped through the `RTO List` region column directly. Tata AIG `CV` is
    `load_cv` in `tata_cv_tw.py` (grid `tata-aig/CV`). Readings: README.
  - Terms that depend on things the policy doesn't show (Kaali Peeli, OD discount over 85%, residency
    clause, booking location) are grid dimensions without a fact, so those policies are `ambiguous`.
  - `textrules`: "All % on Net Premium" is a premium basis, not an unreadable term.
  - Tests: `test_reliance_cv.py` (12), `test_tata_cv.py` (8), one `test_textrules.py` case.
- **PO decisions, 2026-11-23 (after T15).**
  - Buses stay as built (rate depends on who runs the bus; not extracted). Revisit only if needed.
  - Reliance residency clause: the 2.5% cut is applied to every heavy goods vehicle (12 t and over), no
    longer a condition the policy must show. Heavy-goods SATP now resolves; COMP stays `ambiguous` (OD
    discount over 85%) (`test_heavy_goods_take_the_residency_cut_and_comp_depends_on_the_od_discount`).
  - Taxis stay `ambiguous` where a Kaali Peeli rate differs, but the reason names both rates and cells
    (Reliance: a `flat` term per taxi column instead of a rule; Go Digit: the Kaali peeli row's rate).
- **T16 (README).** Architecture (parts, run flow, failure modes, trade-offs), sample results with links,
  a trace-step → code map and the AC22 record were added. Sample outputs were regenerated on the latest
  code (rules extractor): same statuses, rates, citations and traces; only the run time changed.
- **Repository clean-up (PO, 2026-11-23).** AI coding-assistant configuration (assistant instructions and
  settings, plugin workflows, evals and monitoring) is no longer part of the repository; the history was
  rewritten to remove it and the commit trailers that referred to it. The working branch is now `main`
  and `deploy/aws/bootstrap.sh` defaults to it.

