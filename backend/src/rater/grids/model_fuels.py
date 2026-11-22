"""Model → fuel reference list (PO decision 2026-11-22), used only when the policy prints no fuel.

The list is `data/model_fuels.csv` (columns `make,model,fuels,years,source`), built and checked by the PO
outside this repo. Each row lists every fuel the model has been sold in, in India. Only a model sold in a
single fuel supplies a fuel; a printed fuel always wins, and a printed CNG/LPG kit amount above zero blocks
a petrol-only reading (see `extraction.normalise._fuel_from_model`). README assumption.

Matching: the policy's model, with any make glued to its front removed, must start with the listed model
name (spaces and punctuation ignored); the longest listed name wins, so "BOLERO NEO" beats "BOLERO" and
"800" never matches inside "ALTO 800".
"""

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rater.grids.makes import canonical_make

SOURCE = "model → fuel reference list (rater/grids/data/model_fuels.csv)"
ALLOWED = frozenset({"petrol", "diesel", "cng", "lpg", "electric", "hybrid"})
_CSV = Path(__file__).with_name("data") / "model_fuels.csv"


@dataclass(frozen=True)
class Entry:
    make: str
    model: str
    fuels: frozenset[str]
    years: str
    source: str


def _squash(text: str) -> str:
    return "".join(ch for ch in str(text).upper() if ch.isalnum())


@lru_cache(maxsize=1)
def entries() -> tuple[Entry, ...]:
    out = []
    with _CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fuels = frozenset(x.strip().lower() for x in row["fuels"].split("|") if x.strip())
            if not fuels <= ALLOWED:
                raise ValueError(f"model_fuels.csv: unknown fuel in {row}")
            out.append(
                Entry(
                    row["make"].strip().upper(),
                    row["model"].strip().upper(),
                    fuels,
                    row["years"].strip(),
                    row["source"].strip(),
                )
            )
    return tuple(out)


@lru_cache(maxsize=1)
def _index() -> tuple[tuple[str, str, frozenset[str]], ...]:
    rows = [(_squash(canonical_make(e.make)), _squash(e.model), e.fuels) for e in entries()]
    return tuple(sorted(rows, key=lambda r: -len(r[1])))


def fuels_for(make: str, model: str) -> frozenset[str] | None:
    """Fuels the model is sold in, or None when it isn't listed. An "EV"/"Electric" model is electric."""
    words = str(model).upper().replace("-", " ").split()
    if "EV" in words or "ELECTRIC" in words:
        return frozenset({"electric"})
    mk = _squash(canonical_make(make))
    m = _squash(model)
    if mk and m.startswith(mk) and len(m) > len(mk):
        m = m[len(mk) :]  # "MAHINDRABOLERONEO…" → "BOLERONEO…"
    for list_make, key, fuels in _index():
        if list_make == mk and m.startswith(key):
            return fuels
    return None
