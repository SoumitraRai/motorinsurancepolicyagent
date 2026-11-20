# Vaatun INS/001 — Insurance Rater Agent: Build Spec (v2)

## 0. Source of truth (read this first)

1. **`insurance-rater-agent-challenge/challenge.md`** is the official brief, shipped in the starter bundle. **If this file and challenge.md disagree, challenge.md wins.** Flag the conflict; don't resolve it silently.
2. https://solvetojoin.vaatun.com/ is the challenge page. It has the same content plus the example result JSON (§6).
3. This file restructures both for build work and adds bundle facts checked on disk (§5).

The bundle folder `insurance-rater-agent-challenge/` is **read-only input**. Don't edit, move or rename anything in it. `MANIFEST.json` has the SHA-256 of every file, so verify against it in a test.

---

## 1. What you are building

A hosted web app. A reviewer uploads a **motor policy PDF** and gets back the **broker commission (brokerage) percentage** the insurer pays, for OD and TP separately. The rate is looked up deterministically in the supplied insurer grids, and every step is cited to its exact source.

- The commission is paid by the insurer to the broker. It is **not** the customer's price or a discount.
- A commission grid / brokerage grid / rate card is a conditional lookup table. Treat the grids as authoritative.
- `raters/` is a folder of grid files, not rating software.
- No deadline, no prescribed stack.

## 2. Domain essentials

- **OD (Own Damage):** damage to the insured vehicle (accident, theft, fire).
- **TP (Third Party):** legal liability for injury or damage to others.
- **Comprehensive / package** = OD + TP. **Stand-alone TP (SATP)** = TP only, so OD is **not applicable, never 0%**.
- Each rate applies only to its own premium component. Other components (roadside assistance, paid driver, CNG kit) are not rated. Percentages are required; rupee amounts are optional.

| Term | Meaning |
|---|---|
| RTO | Regional Transport Office. The registration code is a geographic key; insurers group RTOs into zones/clusters. |
| CC | Engine capacity, usually banded. |
| NCB | No Claim Bonus, a claim-free OD discount. Some grids use the NCB % as a lookup condition. |
| Business type | **Same insurer as both current and previous insurer → renewal**, not new business or rollover/ported. |
| Premium slab | A range bucket on a premium amount. |
| Vehicle segment | Insurer-defined bucket: model, fuel, CC, age, or a combination. |

Grids may depend on: RTO/zone, make and model, fuel, CC, vehicle age, policy type, business type, NCB, premium slabs, and footnotes.

## 3. Pipeline

1. **Extract** the policy facts that affect brokerage, with a page citation per fact.
2. **Select** the right grid for the insurer and product (private car, and comprehensive vs SATP).
3. **Map** facts into grid vocabulary (RTO → zone/cluster, make/model → segment), citing every mapping cell.
4. **Match** the row/cell where **every** required dimension matches.
5. **Apply exceptions** (footnotes, declines, exclusions, T&C) before answering. An exception overrides an apparently matching cell.
6. **Return** status, OD/TP rates with applicability, citations, confidence, and an ordered trace.

The worked example on the site and in challenge.md (HR-26 → Zone A, Segment H1, OD 12% / TP 2%, `fictional-grid.xlsx`) is **fictional**. None of its values are answers. Use it only to understand the shape of a trace.

## 4. Requirements

**R1 — Facts.** Extract insurer, previous insurer and business type (where relevant), make/model, fuel, RTO, CC, manufacture year *or* vehicle age, policy type, NCB, and premium breakup. **Preserve uncertainty**: an unknown stays unknown and is never guessed.

**R2 — Status.** Exactly one of `resolved` | `unsupported` | `ambiguous`, with **OD and TP applicability reported separately**.

**R3 — Citations.**
- Policy facts: file + page.
- Mapping steps: file + sheet + cell/range.
- Final rate: **XLSX** → file, sheet, cell/range; **PDF grid** → file, page, **table row**.
- "Found in the grid" is not a citation.

**R4 — Deterministic boundary (hard rule).** LLMs may be used for **document extraction only**. Grid selection, mapping, matching and exceptions are plain code: reproducible, unit-tested, explainable. **Never infer through** a missing, declined, contradictory or out-of-scope rule. Return `unsupported`/`ambiguous` with the evidence instead.

**R5 — Unseen policies.** Upload happens in the **deployed browser frontend**. Reviewers will upload policies you haven't seen. A CLI or local-path interface is fine for development but doesn't count. **Never hard-code answers for the four samples.** Supporting policy URLs or new grid uploads is optional. The `raters/` files may be packaged with the deployment.

**R6 — Persistent history.** Uploaded PDFs and completed analyses must stay visible in the frontend after a browser refresh, closing and reopening the app, sign-out/in (if auth exists), and an **app/server/container restart or redeploy**. Container-local or ephemeral storage alone fails. The README must say where PDFs and analyses are stored and how they persist across each of those events.

**Clarifying questions.** The agent *may* ask the user a clarifying question when a required policy fact is genuinely ambiguous. That's optional; returning `ambiguous` is always acceptable.

**Frontend must show:** status, rates, citations, confidence, and the decision trace.

## 5. Bundle contents (verified on disk)

```
insurance-rater-agent-challenge/
├── README.md, challenge.md, MANIFEST.json
├── sample-policies/
│   ├── pvt-car-comprehensive-hdfc-ergo.pdf
│   ├── pvt-car-satp-go-digit.pdf
│   ├── pvt-car-comprehensive-reliance.pdf
│   └── pvt-car-satp-tata-aig.pdf
└── raters/
    ├── hdfc-ergo/feb-2025/Pvt Car New Grid Eff 1st Feb'25 (HDFC ergo) 1.pdf
    ├── godigit/march-2026/Large Insurance Brokers Mar'26 - Shared.xlsx
    ├── reliance-indusind/feb-2026/Reliance Broking Premier  FEB 26 Grid.xlsx
    └── tata-aig/march-2026/Tata AIG Standard Grid_Communication_Mar'26_F_v2_0212.xlsx
```

**Workbook sheets.** These are the exact names; some contain **double spaces or trailing spaces**, so cite them exactly.

- **Go Digit (14 sheets):** `CV Grid (excl. HCV)`, `HCV GRID`, `TAXI Segments and Location wise`, `4W SATP`, `4W New Business 1+3`, `TW 1+1 & SATP`, `TW 1+5`, `2W Grid 5+5`, `TW SAOD with Flexi Options`, `School & Staff Bus ` (trailing space), `School & Staff Bus RTO`, `CV RTO Mapping`, `2W RTO's`, `4W  RTO` (two spaces)
- **Reliance (8 sheets):** `FEB'26 - Grid`, `TW SCOOTER GRID`, `PRIVATE CAR COMP, SAOD & STP`, `Short Term Taxi`, `Enabler, PO Guidelines & T&C`, `Contest`, `RTO List`, `Make Model wise segment`
- **Tata AIG (7 sheets):** `General Guidelines`, `cv checks`, `pci checks`, `Pvtcar` (70 columns), `CV`, `TW`, `Pvtcar_Extended Warranty`

Most sheets cover other products (commercial vehicles, two-wheelers, taxis, buses, extended warranty). All four samples are **private cars**. I picked out the candidate sheets above from their names only. Confirm which sheets apply by reading them, and treat guideline/T&C/checks sheets as possible sources of exceptions.

**Notes from the bundle README:** file metadata has been sanitized, but the original layouts, **formulas, cached values**, sheets and lookup content are retained. Decide deliberately whether to read cached values or formulas, and document the choice. Grid folders are dated (HDFC ERGO Feb 2025; the others Feb/Mar 2026). Whether the policy's dates need to fall inside a grid's effective period isn't stated anywhere. Investigate it and document what you decide.

**Test bench** (expected behaviour, not answers):

| # | File | Tests |
|---|---|---|
| 1 | pvt-car-comprehensive-hdfc-ergo.pdf | Map geography, then OD rate: zone × OD premium slab × fuel × NCB (PDF grid) |
| 2 | pvt-car-satp-go-digit.pdf | TP-only vehicle bucket: RTO cluster × fuel/CC segment |
| 3 | pvt-car-comprehensive-reliance.pdf | Identify the model, then obey the footnote: RTO zone × model segment × exception |
| 4 | pvt-car-satp-tata-aig.pdf | **Prove why no supported rate exists**: TP-only coverage-gap detection |

Knowing when the evidence can't support an answer is part of the problem. A confident, evidenced refusal scores as accuracy.

## 6. Output contract

The page gives this example. **The schema may differ**, but applicability, evidence and uncertainty must be explicit:

```json
{
  "status": "resolved",
  "facts": { "policyType": "comprehensive", "rto": "HR-26", "fuel": "petrol" },
  "rates": {
    "od": { "applicable": true, "ratePercent": 12 },
    "tp": { "applicable": true, "ratePercent": 2 }
  },
  "trace": [
    { "decision": "HR-26 maps to Zone A",
      "policyCitation": "fictional-policy.pdf · page 1",
      "gridCitation": "fictional-grid.xlsx · Geography!B14:C14" },
    { "decision": "Vehicle maps to Segment H1",
      "gridCitation": "fictional-grid.xlsx · Vehicles!D8:F8" },
    { "decision": "OD 12%; TP 2%; diesel exclusion does not apply",
      "gridCitation": "fictional-grid.xlsx · Rates!G22:H22; A27:H27" }
  ],
  "confidence": { "level": "high", "reason": "Every required fact and mapping was found" }
}
```

A real result must also carry **all** R1 facts, each with its page citation and uncertainty, plus an ordered human-readable trace and a confidence level with a short reason.

## 7. Evaluation

**Baseline gate (pass/fail, checked first):** the app is deployed, processes policy PDFs beyond the samples, and keeps history across refresh, re-login, restart and redeploy. Fail any of these and the submission isn't scored.

| Weight | Criterion |
|---|---|
| 40% | Accuracy: correct extraction and rate, or the correct evidence-backed refusal |
| 25% | Traceability: inspectable transformations, granular citations |
| 20% | Resilience: missing fields, exclusions, footnotes, ambiguity, unsupported segments |
| 15% | Engineering: readable code, useful tests, sensible boundaries, clear docs |

## 8. Submission checklist

- [ ] Browser frontend deployed at a hosted URL
- [ ] Upload flow that works on unseen policy PDFs
- [ ] History (PDFs + analyses) survives refresh, reopen, re-login, restart, redeploy
- [ ] Source repository
- [ ] README: setup, run and deploy instructions
- [ ] README: where PDFs and analyses are stored and how they persist
- [ ] Automated tests for the **rating logic** and the **storage boundary**
- [ ] Structured outputs + decision traces for all 4 samples, committed and easy to find
- [ ] Short note: architecture, assumptions, failure modes, trade-offs
- [ ] Email **careers@vaatun.com**, subject **`Insurance Rater Agent Challenge Submission`**, with the hosted URL, the repo link, and direct links to the 4 traces if they're not obvious. Include credentials if sign-in is needed.

## 9. Still open (decide, then document in the README)

- Stack, hosting, and durable storage backend(s)
- Auth or none (if you add it, R6 must hold across sign-out/in)
- Final output schema (extend §6; keep its keys recognisable)
- Confidence scale and its rules
- Extraction LLM and how its output is validated against the PDF text
- Whether to support clarifying questions or only return `ambiguous`
- Grid effective-date handling
- Formula vs cached-value reading for XLSX; table-row extraction for the HDFC ERGO PDF grid
