"""Load every grid adapter's rules, only after the bundle passes its SHA-256 check (spec SR11)."""

from pathlib import Path

from rater.bundle import verify_bundle
from rater.grids.adapters import godigit_4w, hdfc_pvtcar_pdf, reliance_pvtcar, tata_pvtcar
from rater.grids.model import GridSet
from rater.insurers import ALIASES

ADAPTERS = (hdfc_pvtcar_pdf, godigit_4w, reliance_pvtcar, tata_pvtcar)


def load_all(root: Path) -> GridSet:
    verify_bundle(root)
    grids = tuple(g for adapter in ADAPTERS for g in adapter.load(root))
    return GridSet(
        grids=grids, aliases={k: v for k, v in ALIASES.items() if any(g.insurer == k for g in grids)}
    )
