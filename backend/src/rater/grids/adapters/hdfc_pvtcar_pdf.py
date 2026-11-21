"""HDFC ERGO private-car grid (PDF, 2 pages): zone rate tables × OD-premium slab × fuel × NCB, and a
state → zone table. Column meanings come from the PDF's own header lines; fuel groups from its footnotes.
"""

import re
from datetime import date
from pathlib import Path

from rater.citations import PdfGridCite
from rater.grids.bands import parse_band
from rater.grids.model import (
    CitySplitTable,
    ExceptionRule,
    Grid,
    MappingRow,
    RateCell,
    RateRule,
    Unpublished,
)
from rater.grids.pdfgrid import Line, Word, pdf_lines
from rater.grids.textrules import classify
from rater.resolve.confidence import Cap

INSURER = "HDFC ERGO"
_PCT = re.compile(r"^\d+(?:\.\d+)?%$")
_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}
_FUEL_WORDS = {
    "diesel": "diesel",
    "cng": "cng",
    "lpg": "lpg",
    "ev": "electric",
    "electric": "electric",
    "hybrid": "hybrid",
    "petrol": "petrol",
}
# Spelling aliases between the PDF's state names and the state-code table (README assumption).
_STATE_ALIASES = {"J&K": "JAMMU AND KASHMIR"}


def _groups(words: tuple[Word, ...], gap: float = 12.0) -> list[tuple[str, float]]:
    """Adjacent words joined into labels, each with its centre x."""
    out: list[list[Word]] = []
    for w in words:
        if out and w.x0 - out[-1][-1].x1 <= gap:
            out[-1].append(w)
        else:
            out.append([w])
    return [(" ".join(w.text for w in g), (g[0].x0 + g[-1].x1) / 2) for g in out]


def _nearest(x: float, labels: list[tuple[str, float]]) -> str:
    return min(labels, key=lambda lc: abs(lc[1] - x))[0]


def _fuels(label: str, defs: dict[str, frozenset[str]]) -> frozenset[str]:
    key = "non-petrol" if "non" in label.lower() else "petrol"
    return defs[key]


def _ncb(label: str) -> frozenset[str]:
    norm = label.replace(" ", "").upper()
    if norm == "NCB&N-NCB":
        return frozenset({"ncb", "no_ncb"})
    return frozenset({"no_ncb"}) if norm.startswith("N-") else frozenset({"ncb"})


def _parse_date(text: str) -> date | None:
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*'?(\d{2,4})", text)
    if not m:
        return None
    day, mon, year = int(m.group(1)), _MONTHS.get(m.group(2).lower()), int(m.group(3))
    return date(year + 2000 if year < 100 else year, mon, day) if mon else None


def _definitions(lines: list[Line]) -> dict[str, frozenset[str]]:
    petrol, non = {"petrol"}, set()
    for ln in lines:
        t = ln.text.lstrip("*# ")
        m = re.match(r"Non\s*Petrol includes (.+)", t, re.I)
        if m:
            non |= {
                _FUEL_WORDS[w.lower()]
                for w in re.split(r"[,\s]+(?:and\s+)?", m.group(1))
                if w.lower() in _FUEL_WORDS
            }
        m = re.match(r"(.+?) is to be considered in Petrol Grid", t, re.I)
        if m:
            petrol |= {
                _FUEL_WORDS[w.lower()]
                for w in re.split(r"\s+and\s+|[,\s]+", m.group(1))
                if w.lower() in _FUEL_WORDS
            }
    return {"petrol": frozenset(petrol), "non-petrol": frozenset(non or {"diesel", "cng", "lpg"})}


def load(root: Path) -> list[Grid]:
    path = next((root / "raters" / "hdfc-ergo").rglob("*.pdf"))
    file = path.relative_to(root).as_posix()
    lines = pdf_lines(path)
    defs = _definitions(lines)
    footnotes = [ln for ln in lines if ln.page == 1 and ln.text.lstrip().startswith(("*", "#", "Slab"))]

    rules: list[RateRule] = []
    zone: str | None = None
    policy_hdr: list[tuple[str, float]] = []
    fuel_hdr: list[tuple[str, float]] = []
    ncb_hdr: list[tuple[str, float]] = []
    date_line = next(ln for ln in lines if ln.text.lower().startswith("effective from"))
    for ln in (x for x in lines if x.page == 1):
        text = ln.text.strip()
        if re.fullmatch(r"Zone \d", text):
            zone = text
        elif text.startswith("Package"):
            policy_hdr = _groups(ln.words, gap=60)
        elif ln.words[0].text.startswith("Petrol") or (len(ln.words) > 1 and ln.words[1].text == "Petrol"):
            fuel_hdr = _groups(ln.words)
        elif text.startswith("NCB"):
            ncb_hdr = _groups(ln.words)
        elif zone and len(ln.words) > 1 and all(_PCT.match(w.text) for w in ln.words[1:]):
            slab = ln.words[0].text
            band = parse_band(slab, "inr")
            if band is None:
                raise ValueError(f"HDFC ERGO: unreadable slab label {slab!r} on page {ln.page}")
            for w in ln.words[1:]:
                x = (w.x0 + w.x1) / 2
                policy = _nearest(x, policy_hdr)
                fuel = _nearest(x, fuel_hdr)
                ncb = _nearest(x, ncb_hdr)
                table = f"{zone} / {policy} / {fuel} / {ncb}"
                cite = PdfGridCite(file, ln.page, table, slab)
                rules.append(
                    RateRule(
                        dims=(
                            ("fuel", _fuels(fuel, defs)),
                            ("ncb_flag", _ncb(ncb)),
                            ("od_premium", band),
                            ("policy_type", "comprehensive" if policy == "Package" else "saod"),
                            ("zone", zone),
                        ),
                        od=RateCell(float(w.text.rstrip("%")), w.text, cite),
                        tp=None,
                        cite=cite,
                        label=f"{zone} · {policy} · {fuel} · {ncb} · OD premium {slab}",
                    )
                )

    states: list[MappingRow] = []
    state: str | None = None
    for ln in lines:
        if "Zone-1" in ln.text or ln.page == 1 and ln.y < 600:
            continue
        name = " ".join(w.text for w in ln.words if 150 <= w.x0 < 265)
        z1 = " ".join(w.text for w in ln.words if 265 <= w.x0 < 420)
        z2 = " ".join(w.text for w in ln.words if w.x0 >= 420)
        if name:
            state = _STATE_ALIASES.get(name.upper(), name.upper())
        if state is None:
            continue
        for entry, value in ((z1, "Zone 1"), (z2, "Zone 2")):
            if not entry:
                continue
            if entry.upper() == state or _STATE_ALIASES.get(entry.upper()) == state:
                key = state
            elif entry.lower().startswith("rest of"):
                key = f"{state}|*"
            else:
                key = f"{state}|{entry.upper()}"
            states.append(
                MappingRow(key, value, PdfGridCite(file, ln.page, "State → zone", entry), raw=entry)
            )

    exceptions = []
    caps = []
    for ln in footnotes:
        c = classify(ln.text, "private_car")
        cite = PdfGridCite(file, ln.page, "Footnotes", ln.text)
        if c.kind == "slab_basis":
            caps.append(
                Cap(
                    "medium",
                    "HDFC ERGO slab footnote mentions GWP / slab achievement; the policy's OD "
                    "premium was used as the slab (C1)",
                )
            )
        exceptions.append(ExceptionRule(c.kind, c.text, cite, effect=c.effect, percent=c.percent))

    date_cite = PdfGridCite(file, date_line.page, "Header", date_line.text)
    package_cite = PdfGridCite(file, 1, "Zone 1 / Package", "Package")
    return [
        Grid(
            id="hdfc-ergo/pvt-car",
            insurer=INSURER,
            file=file,
            title="HDFC ERGO private car grid (PDF)",
            vehicle_classes=frozenset({"private_car"}),
            policy_types=frozenset({"comprehensive", "saod"}),
            rules=tuple(rules),
            mappings=(CitySplitTable(name="HDFC ERGO state → zone", target="zone", rows=tuple(states)),),
            exceptions=tuple(e for e in exceptions if e.kind != "slab_basis")
            + tuple(e for e in exceptions if e.kind == "slab_basis"),
            unpublished=(
                Unpublished(
                    "comprehensive",
                    "tp",
                    "HDFC ERGO's grid publishes package (OD) rates only; no TP rate is published",
                    package_cite,
                ),
            ),
            effective_from=_parse_date(date_line.text),
            date_text=date_line.text,
            date_cite=date_cite,
            caps=tuple(caps),
            new_business_counts_as_ncb=any(
                "new business will be considered as ncb" in ln.text.lower() for ln in footnotes
            ),
        )
    ]
