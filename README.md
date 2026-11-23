# Brokerage Rate Agent (Vaatun INS/001)

Upload a motor insurance policy PDF in the browser; the app returns the broker commission (brokerage)
percentage the insurer pays, for **OD** and **TP** separately, with every step cited to the exact source:
policy page → grid mapping cell → rate cell → footnote. Runs end as `resolved`, `unsupported` or
`ambiguous`; a confident, evidenced refusal is a valid answer.

- **Sample outputs** (structured JSON + readable trace for the four supplied policies):
  [`samples/output/`](samples/output/) — see [Sample results](#sample-results).
- **Requirements trail:** [`sdlc/changes/2026-11-20-brokerage-rate-agent/`](sdlc/changes/2026-11-20-brokerage-rate-agent/)
  (`intent.md` → `spec.md` → `plan.md`, with every departure recorded).

## How it works

```
browser (React) ──upload──▶ FastAPI ──▶ Supabase Storage (PDF) + Postgres (run, job)
                                  ▲                        │
            history / run page ───┘                        ▼
                                              worker (claims job, SKIP LOCKED)
                                                           │
     1. OCR every image page locally: RapidOCR (main) + Tesseract (cross-check); text layer if present
     2. Extract facts: an LLM via OpenRouter (if configured) or the local rules extractor (fallback)
        – each fact = value + page + verbatim quote
     3. Code checks every quote against that page's text, then normalises values (dates, RTO, cc, ₹ …)
     4. Deterministic resolution against the original grid files (no LLM):
        select grid → effective-date check → map RTO/model into grid vocabulary → match the row
        where every dimension matches → apply footnotes / T&C → result + citations + confidence
```

The LLM is used **only** to propose facts with quotes. Grid selection, mapping, matching and exceptions
are plain Python (`backend/src/rater/resolve/`), pure functions tested against synthetic grids. The
original grids are read in code from `insurance-rater-agent-challenge/raters/` (one adapter per sheet
layout in `backend/src/rater/grids/adapters/`) after their SHA-256s are verified against `MANIFEST.json`.

## Where uploads and analyses are stored, and why they persist

| What | Where | Survives |
|---|---|---|
| Uploaded PDF | Supabase Storage, private bucket `policies`, key `<uuid>/<sha256>.pdf` | everything below |
| Run, status, full result JSON, switches, versions | Supabase Postgres table `runs` (+ `jobs`, `audit_events`) | everything below |
| Containers (web, worker, Caddy) | one AWS EC2 host (Mumbai); app containers are **stateless**, no local data | — |

- **Browser refresh / close and reopen:** history is read from Postgres on every page load (`GET /api/runs`).
- **Sign-out / sign-in:** runs belong to the reviewer's Supabase user id, not to the browser session.
- **Server or container restart, redeploy:** containers keep nothing; Postgres and Storage are managed
  services outside the containers. A job interrupted by a restart is reclaimed after its lock times out.

## Run locally

Prerequisites: Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 22, Docker (tests start Postgres 16),
Tesseract (`brew install tesseract` / `apt-get install tesseract-ocr`).

```bash
make build      # backend deps + frontend build            → "Build succeeded"
make test       # unit + integration tests (Docker needed) → "… passed"
make lint       # ruff, mypy, eslint, tsc, sample-answer guard → "All checks passed"
make e2e        # the four sample policies end to end (slow: ~3–4 min of OCR)
```

Analyse one PDF from the command line (development only; the browser upload is the product):

```bash
cd backend && uv run python -m rater.cli run ../insurance-rater-agent-challenge/sample-policies/<file>.pdf \
  --out ../samples/output/<file>
```

## Deploy (AWS EC2 + Supabase)

The hosted app runs on one EC2 host with Docker Compose (`deploy/aws/`): the web API, the worker and
Caddy (automatic HTTPS). Both OCR engines together peak at ≈1.2 GB, so the host needs 4 GB of RAM.

1. **Supabase:** create a project (Mumbai, `ap-south-1`). Run `migrations/*.sql` in order. Create a
   **private** Storage bucket `policies`. Under Authentication: use asymmetric JWT signing keys (the API
   verifies tokens against the project's JWKS), disable sign-ups, and create the reviewer user.
2. **EC2:** in `ap-south-1`, launch Ubuntu 24.04 (x86_64) on `c7i-flex.large` (2 vCPU, 4 GB) with a
   30 GB gp3 disk. Security group: SSH (22) from your IP only, HTTP (80) and HTTPS (443) from anywhere.
   Attach an Elastic IP so the address survives restarts.
3. **On the host:**
   ```bash
   curl -fsSL https://raw.githubusercontent.com/SoumitraRai/motorinsurancepolicyagent/sdlc/2026-11-20-brokerage-rate-agent/deploy/aws/bootstrap.sh | bash
   sudo cp /opt/rater/app/deploy/aws/env.template /opt/rater/rater.env
   sudo chmod 600 /opt/rater/rater.env && sudo nano /opt/rater/rater.env   # fill in the values
   /opt/rater/app/deploy/aws/deploy.sh
   ```
   `SITE_ADDRESS` can be `<elastic-ip-with-dashes>.sslip.io`; Caddy fetches its certificate on first start.
4. Sign in at `https://<SITE_ADDRESS>` and upload a policy. To update: re-run `bootstrap.sh`, then
   `deploy.sh`.

`render.yaml` describes the same two services on Render; it is kept but not used (Render's plans with
enough memory are paid).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `EXTRACTION_PROVIDER` | `openrouter` | `rules` forces the local extractor |
| `OPENROUTER_API_KEY`, `EXTRACTION_MODEL` | unset | both needed for LLM extraction; otherwise local rules |
| `GRID_DATE_POLICY` | `strict` | D1 (Vaatun, 2026-11-22): outside a grid's stated period → `unsupported` with the reason; `warn` → warning + lower confidence |
| `BROKER_ELIGIBILITY` | `assume_base` | D2: broker qualifies for base rates; volume bonuses listed, never added; `require_evidence` → refuse |
| `LESSER_PERCENT_MEANS` | `points` | C2: "5% lesser" = 5 percentage points; `relative` = 5% of the rate |
| `OCR_WORKERS` | `1` | pages OCR'd in parallel (each ≈1 GB) |
| `READ_PAGES` | `20` | only the first N pages are OCR'd and extracted; `0` = all. Uploads may have up to 200 pages. Vaatun said the key details are in the first 5–6 pages, but the Tata AIG sample prints the insurer only on page 12 and Reliance the previous insurer on page 13, so 6 would lose them |

Every run records the switch values in `meta.switches`.

## Data and privacy

Uploaded PDFs and extracted facts are treated as restricted. They are stored only in Supabase (private
bucket; row-level filtering by user), and — **only when `OPENROUTER_API_KEY` is set** — page images and
OCR text are sent to OpenRouter and its upstream model provider for extraction. With the local rules
extractor nothing leaves our infrastructure. Logs contain run ids, step names and durations only, never
policy values or quotes.

## Assumptions and decisions

Every decision below is recorded with its source in
[`intent.md`](sdlc/changes/2026-11-20-brokerage-rate-agent/intent.md) (A = brief, B = product owner,
D = default pending Vaatun) and [`spec.md`](sdlc/changes/2026-11-20-brokerage-rate-agent/spec.md) (C1–C13).

**Results and refusals**
- An LLM is used for extraction only. Grid selection, mapping, matching and exceptions are deterministic code.
- A missing, declined, contradictory or out-of-scope rule is never inferred through. The run ends
  `unsupported` or `ambiguous`, with the evidence.
- Stand-alone TP: OD is `{"applicable": false, "ratePercent": null}`, never 0%.
- **TP for package policies (C3).** Three grids publish package rates on the OD premium only (HDFC ERGO,
  Reliance, Tata AIG). TP is then `applicable: true, ratePercent: null`, with the grid cell cited.
- **Unknown facts that cannot change the rate.** If a fact with a closed set of values (fuel, NCB yes/no,
  add-ons, CPA, business type) is not printed, but every value the grid lists gives the same rate, the
  result is resolved and the trace says so. If the rates differ, the result is `ambiguous` and the run page
  asks the reviewer for the fact (SR25).

**Reading the grids**
- **XLSX:** stored (cached) cell values only, never formulas. A formula with no stored value is missing.
- **Band gaps:** a value at an uncovered boundary is `ambiguous` (e.g. exactly 1000 cc between `<1000` and
  `>1000`).

**Insurer-specific readings**
- **HDFC ERGO slab (C1):** the policy's OD premium is used as the slab key, although the footnote mentions
  GWP. Confidence is capped at medium.
- **Go Digit:**
  - "Max CD2" is reported as the rate, labelled as the insurer's published maximum (C7).
  - Notes that decline "few RTOs" without naming them make a matching policy `ambiguous` (C5).
  - The new-business CD2 is applied to OD, because its basis is not stated (confidence capped).
- **Reliance:** "5% lesser" means 5 percentage points (`LESSER_PERCENT_MEANS`, C2). Region names in its
  `RTO List` are linked to rate rows by spelling or abbreviation, then by the city → state list. Its
  zone must agree, otherwise the result is `ambiguous`.
- **Tata AIG:**
  - Its workbook has no make/model → segment table, so a policy that does not print its segment is
    `unsupported` (C8).
  - "Other Than Diesel" means petrol/LPG/hybrid; CNG and Electric have their own rows.

- **Go Digit commercial vehicles (`CV Grid (excl. HCV)`):**
  - Goods vehicles pick the LCV / MCV / HCV column of `CV RTO Mapping` by gross vehicle weight, using the
    Motor Vehicles Act classes (up to 7.5 t, up to 12 t, above 12 t), since the sheet doesn't define them.
  - Tractors use the Misc D column (there is no tractor column); confidence is capped at medium.
  - Grid cluster names that differ from the mapping only in spelling are linked. Names that differ in
    substance (`KA 1 Good` vs `KA1 (EX BLR)`, `DELHI-1`) are not guessed: the result is `unsupported`.
  - A rate cell with several rates depends on the OD discount (CD1) chosen, which the policy doesn't show:
    `ambiguous`.

**Reference data and switches**
- **Reference lists (PO decisions), each confidence-capped at medium when used:**
  - RTO state codes and a city → state list (`backend/src/rater/grids/geo.py`);
  - a model → fuel list, single-fuel models only (`backend/src/rater/grids/data/model_fuels.csv`, with a
    source per row; built and checked by the product owner; most rows are marked "not web-verified");
  - make spelling aliases (`backend/src/rater/grids/makes.py`).
- **Dates (D1, Vaatun 2026-11-22):** a policy dated outside a grid's stated period is `unsupported`, with
  the period and the policy date in the reason. A grid that states no period is used, and the trace says so.
  If the policy date can't be read, the result is `ambiguous`, unless the policy is `unsupported` for
  another reason anyway (the date couldn't change that).
- **Business type (Vaatun 2026-11-22):** when it can't be established, every value (new, renewal,
  rollover) is tried. If all give the same rates, the result is resolved and the trace says so; otherwise
  it is `ambiguous` and the reviewer is asked.
- **Broker eligibility (D2):** base rates are assumed. Volume, GWP and synergy bonuses are listed as
  "possible, not applied".
- **Policy skills (C11):** the organisation policy files are unfilled templates and were applied in
  spirit (generic controls).
