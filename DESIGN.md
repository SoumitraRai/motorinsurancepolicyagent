---
name: Brokerage Rate Agent
description: A motor policy's OD and TP brokerage, printed as a serial-numbered security-paper rate schedule with a citation under every figure.
colors:
  ink: "#1C2440"
  ink-soft: "#3A4262"
  ink-muted: "#545C78"
  rule: "#D9DEE8"
  rule-strong: "#B8C0D2"
  sheet: "#FFFFFF"
  sheet-wash: "#F6F8FB"
  guard: "#2E7D6F"
  guard-deep: "#1F5E53"
  guard-tint: "#E2F0EA"
  quote: "#F5E1E7"
  serial: "#C62828"
  warn: "#7A4F00"
  warn-tint: "#FFF1D0"
  refuse: "#A3201C"
  refuse-tint: "#FBE8E8"
typography:
  rate:
    fontFamily: "Hind, system-ui, sans-serif"
    fontSize: "2.75rem"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  headline:
    fontFamily: "Hind, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.333
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Hind, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.556
  body:
    fontFamily: "Hind, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Hind, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.429
  meta:
    fontFamily: "Hind, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
  cite:
    fontFamily: "'JetBrains Mono', ui-monospace, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.375
  serial:
    fontFamily: "'JetBrains Mono', ui-monospace, monospace"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.429
    letterSpacing: "0.025em"
  microprint:
    fontFamily: "'JetBrains Mono', ui-monospace, monospace"
    fontSize: "6px"
    fontWeight: 400
    lineHeight: "10px"
    letterSpacing: "0.08em"
rounded:
  hairline: "2px"
  chip: "4px"
  panel: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  cell: "20px"
  xl: "24px"
  2xl: "32px"
  gutter-lg: "48px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    typography: "{typography.body}"
    rounded: "{rounded.hairline}"
    padding: "0 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.ink-soft}"
  button-quiet:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.hairline}"
    padding: "0 16px"
    height: "44px"
  button-quiet-hover:
    backgroundColor: "{colors.sheet-wash}"
  field:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.hairline}"
    padding: "0 12px"
    height: "44px"
  schedule-panel:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
  schedule-band:
    backgroundColor: "{colors.guard-tint}"
    textColor: "{colors.guard-deep}"
    height: "24px"
  schedule-cell:
    padding: "20px"
  status-resolved:
    backgroundColor: "{colors.guard-tint}"
    textColor: "{colors.guard-deep}"
    rounded: "{rounded.chip}"
    padding: "1px 8px"
  status-unsupported:
    backgroundColor: "{colors.refuse-tint}"
    textColor: "{colors.refuse}"
    rounded: "{rounded.chip}"
    padding: "1px 8px"
  status-ambiguous:
    backgroundColor: "{colors.warn-tint}"
    textColor: "{colors.warn}"
    rounded: "{rounded.chip}"
    padding: "1px 8px"
  status-pending:
    backgroundColor: "{colors.sheet-wash}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.chip}"
    padding: "1px 8px"
  quote:
    backgroundColor: "{colors.quote}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.cite}"
    rounded: "{rounded.hairline}"
    padding: "4px 8px"
  cite:
    textColor: "{colors.guard-deep}"
    typography: "{typography.cite}"
  tab-active:
    textColor: "{colors.ink}"
    height: "44px"
  tab-inactive:
    textColor: "{colors.ink-muted}"
    height: "44px"
---

# Design System: Brokerage Rate Agent

## Overview

**Creative North Star: "The Security-Paper Schedule"**

Every result is printed as the policy's own rate schedule: a pre-numbered, security-banded document on white paper, the kind an insurer issues and a reviewer checks against the source. Navy ink carries the words, a teal guilloché band certifies the panel, security-pink underlays mark text quoted from the PDF, and a red mono serial numbers each run. The surface is a working document, not a dashboard: hairline rules divide cells, tables and trace rows the way they divide a printed form.

Density is moderate and reading-led. One panel (the schedule) is lifted and banded; everything around it is flat paper divided by hairlines. Every figure sits one line above the citation it rests on, in monospace, so the eye moves from number to proof without hunting. Refusals render in the same schedule as resolutions; the panel simply carries a "Why there is no rate" foot instead of numbers.

The system rejects the SaaS card grid of equal tiles and the dashboard of KPI boxes. The schedule's four cells (Status, OD rate, TP rate, Confidence) are one document divided by rules, never four floating cards.

**Key Characteristics:**
- White sheet, navy ink, hairline rules as the main structuring device.
- One lifted, banded, 8px-cornered panel per screen (the schedule, or the sign-in card); everything else flat and 2px-cornered.
- Monospace for anything verbatim: citations, quotes, serials, step and field numbers, JSON.
- Colour is semantic and sparse: teal verifies, pink quotes, red numbers and refuses, amber asks.
- Rates at 44px tabular bold; everything else at reading sizes.

## Colors

A paper-and-ink palette with three security-print accents, each bound to a single meaning.

### Primary
- **Schedule Navy** (#1C2440): body text, headings, rates, and the primary button fill. The ink of the document.
- **Soft Navy** (#3A4262): primary button hover; quote text; secondary prose.
- **Muted Navy** (#545C78): cell labels, metadata, placeholder text, inactive tabs, "Not applicable" rate text.

### Secondary
- **Guilloché Teal** (#2E7D6F): the guard band lattice, the schedule panel's border, the microprint, the focus ring, input carets, and drag-over borders.
- **Deep Guard Teal** (#1F5E53): citation text, band caption, links to evidence ("Open the PDF", "All runs"), resolved status text.
- **Guard Tint** (#E2F0EA): the band's ground, the resolved chip, the current run row in the rail, text selection, upload drag-over.

### Tertiary
- **Security Pink** (#F5E1E7): the underlay for text quoted verbatim from the policy PDF (schedule fields, the confidence cell's weakest-link quote). Nothing else.
- **Serial Red** (#C62828): run serials on the band ("Run C91D27A5"), trace step numbers and schedule field numbers. Always mono.
- **Refusal Red** (#A3201C) on **Refusal Tint** (#FBE8E8): unsupported and failed status chips, the failed-run alert, form and load errors.
- **Query Amber** (#7A4F00) on **Amber Tint** (#FFF1D0): ambiguous status chip, trace-step warnings, and the "Add the missing facts" panel.

### Neutral
- **Sheet** (#FFFFFF): page and panel ground.
- **Sheet Wash** (#F6F8FB): quiet button hover, row hover, the JSON block, the "Why there is no rate" foot, pending chips.
- **Hairline** (#D9DEE8): every divider: header, rail edge, cell rules, table and trace rows, tab baseline.
- **Strong Hairline** (#B8C0D2): input and quiet-button borders, the dashed upload target, scrollbar thumb.

### Named Rules
**The Teal Verifies Rule.** The teal family means "checked against a source": citations, the guard band, links that open evidence, the resolved chip, focus and selection. It never fills a button or decorates a heading.

**The Red Is a Number or a No Rule.** Serial Red appears only on mono serials and step/field numbers; Refusal Red only on refusals, failures and errors. No other red exists.

**The Pink Is Verbatim Rule.** Security Pink sits only under text copied from the policy PDF. If the text is paraphrased, it does not get pink.

## Typography

**Display / Body Font:** Hind (self-hosted, 400/500/600/700; fallback system-ui, sans-serif)
**Label / Mono Font:** JetBrains Mono (self-hosted, 400/500; fallback ui-monospace, monospace)

**Character:** Hind is a plain, slightly humanist grotesque that reads like form copy; JetBrains Mono is the machine voice for anything that must be copied exactly. The pairing separates "what the agent says" from "what the source says".

### Hierarchy
- **Rate** (700, 2.75rem, 1.1, -0.02em, tabular figures): OD and TP rates in the schedule only.
- **Headline** (600, 1.5rem, tight tracking): the run's file name, "Rate a motor policy", "Sign in", and text-only rate states ("Not applicable", "Not published", confidence level).
- **Title** (600, 1.125rem): section heads ("History", "Possible, not applied", "Add the missing facts"). App name in the top bar is 700 at 1.125rem, 1.25rem from 640px.
- **Body** (400, 1rem, 1.5): decisions, reasons, prose. Prose blocks cap at 75ch (60ch on the start screen).
- **Label** (600, 0.875rem): schedule cell labels, trace step kinds, form labels.
- **Meta** (400, 0.8125rem): rail row metadata, field verification lines.
- **Cite** (mono 400, 0.8125rem, 1.375): citations and quotes; wraps anywhere.
- **Serial** (mono 500, 0.875rem, wide tracking): run serial on the band.
- **Microprint** (mono 400, 6px/10px, 0.08em): decorative foot rule, aria-hidden.

### Named Rules
**The Byte-for-Byte Rule.** Citations render exactly as the engine emits them. A run of two or more spaces (a sheet name like `'4W  RTO'`) is kept unbreakable with the word on each side, so no significant space can collapse or vanish at a line end; the rest of a long path still wraps.

**The Mono Means Copied Rule.** Monospace is reserved for verbatim and machine text: citations, PDF quotes, serials, step/field numbers, JSON. Agent-written prose stays in Hind.

## Layout

A full-height app shell: a 64px top bar (name left; Upload, reviewer email, Sign out right) over a two-column body capped at 90rem. From 1024px the left rail is fixed at 22rem with a hairline right edge; the main column takes the rest with 48px side padding (32px from 640px, 16px below). Below 1024px the rail hides on a run page (an "All runs" link replaces it) and drops under the start screen otherwise.

The run page stacks at 32px: header (file name, upload time, pages, Open the PDF), the schedule panel, optional "Possible, not applied" and clarification blocks, then tabs. Schedule cells are 1 column on phones, 2 from 640px, and 4 from 1024px at 0.7fr / 1.15fr / 1.15fr / 1fr. Trace rows use a four-column grid from 768px: 2.5rem number, 7.5rem kind, decision, and a 22rem citation column. Schedule fields are a 2.25rem number / 9.5rem label / value grid, two columns of fields from 1024px.

Spacing follows Tailwind's 4px step: 20px cell padding, 12-16px row padding, 24px gaps between grid columns and tabs. Every interactive target is at least 44px tall, except inline citation buttons (24px).

## Elevation & Depth

Flat paper with one lifted document. Depth comes from hairline rules and tint washes; a single soft, navy-tinted shadow lifts the schedule panel and its sibling, the sign-in card. Nothing else casts a shadow, and no shadow responds to hover.

### Shadow Vocabulary
- **Schedule lift** (`box-shadow: 0 1px 2px rgba(28,36,64,0.06), 0 8px 24px -12px rgba(28,36,64,0.18)`): the schedule panel and the sign-in card only.

### Named Rules
**The One Document Rule.** A screen has at most one lifted panel. If a second element wants a shadow, it should be divided by a hairline instead.

## Shapes

Square-shouldered, print-like geometry. Three radii exist: 8px on the schedule panel and the sign-in card (the band carriers), 4px on status chips, and 2px everywhere else: buttons, fields, the upload target, quote underlays, alert and clarification panels, the JSON block. Borders are 1px hairlines; the schedule panel's border is teal, the upload target's is dashed. The guilloché band is a 120 by 24px tile of eight interlaced sine strokes (0.6px, 75% opacity, teal) repeated horizontally over the guard tint.

**The One Rounded Document Rule.** The 8px corner belongs to banded panels only. A component without a guilloché band never gets it.

## Components

### Buttons
Plain, firm and rectangular.
- **Shape:** near-square corners (2px), min height 44px, 12px side padding (16px from 640px), semibold Hind.
- **Primary:** navy fill, white text; hover shifts to soft navy over 150ms. One per region (Upload a policy PDF, Sign in, Rerun with these facts, Retry this run).
- **Quiet:** white with a strong-hairline border, navy text; hover to sheet wash. Used for Upload and Sign out in the top bar and Download JSON.
- **Disabled:** 60% opacity, not-allowed cursor, label switches to a progress phrase ("Uploading…").
- **Focus:** the global 2px teal outline at 2px offset.

### Status Chips
- **Style:** 1px border, tinted fill, semibold text label, 4px corners; 0.8125rem in the rail, 1rem in the schedule.
- **Tones:** resolved = guard tint / deep teal / teal border; unsupported and failed = refusal tint / refusal red; ambiguous = amber tint / amber; queued = wash / muted navy; processing = wash / navy. The label text always carries the meaning; colour only supports it.

### Schedule Panel (signature)
The rate schedule: one article holding the verdict, both rates and confidence.
- **Frame:** 8px corners, 1px teal border, white, schedule lift shadow.
- **Band:** a 24px guilloché strip over guard tint, then a caption row: "Rate schedule · insurer · policy type" in semibold deep teal on the left, the red mono run serial on the right.
- **Cells:** Status | OD rate | TP rate | Confidence, 20px padding, divided by hairlines. Each rate cell shows the 44px tabular rate, its grid citation directly below, then the reason in muted label text. Text-only states ("Not applicable", "Not published", "No rate", "—") drop to 1.5rem muted semibold.
- **Confidence cell:** level in 1.5rem semibold, weakest-link reason, and that fact's PDF quote on security pink, clamped to four lines.
- **Microprint foot:** a teal top rule carrying "BROKERAGE RATE AGENT RUN XXXXXXXX ·" repeated in 6px mono.
- **Refusal foot:** "Why there is no rate" on sheet wash under a hairline, for unsupported and ambiguous runs.
- **Motion:** when a run finishes while being watched, the band prints once: a 700ms clip-path sweep from 60% to full width, `cubic-bezier(0.16, 1, 0.3, 1)`. Off under reduced motion.

### Sign-in Card
The schedule panel's sibling: same frame and shadow, a taller 40px guilloché band with no caption, then email, password and a full-width primary button, max width 28rem.

### Tabs
- **Style:** text tabs on a hairline baseline, 24px apart, 44px tall. Active: navy semibold with a 2px navy underline sitting on the baseline. Inactive: muted navy, navy on hover.
- **Behaviour:** roving tabindex; arrow keys, Home and End move focus and selection. Labels: Decision trace, Schedule fields, JSON.

### Trace Rows
A numbered list between hairlines, one row per engine decision: red mono two-digit step number, muted semibold kind (Grid, Dates, Mapping, Row, Result), the decision in body text, and its citations in the right column. A policy citation is a button (thin teal underline, solid on hover) that opens the PDF at the cited page. Rows with warnings take a 60% amber tint and an amber "Warning:" line.

### Schedule Fields
Numbered like a printed form: red mono field number, semibold label, value (muted "Not found" when absent), then the verbatim PDF quote on security pink in mono, then a meta line (Page n · verification · confidence). Found fields sort before missing ones.

### Inputs / Fields
- **Style:** white, 1px strong-hairline border, 2px corners, 44px tall, 12px side padding; labels sit above in 0.875rem semibold.
- **Hover:** border darkens to muted navy. **Focus:** global teal outline; caret is teal.
- **Error:** a refusal-red medium-weight message below, announced as an alert.

### Upload Target
Dashed strong-hairline box with 2px corners holding a primary button and a muted hint line. Compact (12px padding) in the rail; large (224px tall, centred) on the start screen. Drag-over turns the border teal and the ground guard tint.

### Navigation (Run Rail)
A table of runs, newest first. Each row: semibold file name (wraps anywhere), insurer, "OD x / TP y" in meta size with tabular values, time, and a status chip right-aligned. The whole row is the link. Hover: sheet wash. Current run: guard tint. Keyboard focus: a 2px teal inset outline on the row.

### Citations
Mono 0.8125rem deep teal, wrap anywhere, double-space runs held together (see The Byte-for-Byte Rule).

## Do's and Don'ts

### Do:
- **Do** put every rate one line above its exact grid citation, and its reason below that.
- **Do** show stand-alone TP OD as "Not applicable" and an unpublished package TP as "Not published" with the grid cell cited.
- **Do** render citations byte-for-byte through the citation component, preserving double spaces in sheet names.
- **Do** keep status readable as text in every chip; colour supports it.
- **Do** use the 8px radius and the schedule lift only on banded panels (the schedule and the sign-in card).
- **Do** divide content with 1px hairlines before reaching for tints, and with tints before shadows.
- **Do** keep every interactive target at least 44px tall and every focus state on the 2px teal outline.
- **Do** honour reduced motion: the band print and loading pulses stop.

### Don't:
- **Don't** show OD on a stand-alone TP policy as 0%; it is "Not applicable".
- **Don't** round, reformat or paraphrase a rate or citation the grid supplies.
- **Don't** split the schedule into separate floating cards or a KPI tile row.
- **Don't** use the teal family as a button fill or decoration; it marks verified sources only.
- **Don't** use red for anything but serials, step and field numbers, refusals and errors.
- **Don't** put Security Pink under paraphrased or agent-written text.
- **Don't** add a second shadowed or 8px-cornered panel to a screen.
- **Don't** add Vaatun or insurer branding; insurer names appear only as data.
