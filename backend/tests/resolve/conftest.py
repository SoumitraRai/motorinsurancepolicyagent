"""Synthetic grids and facts for resolver tests. Nothing here comes from the supplied files (NN5)."""

from datetime import date
from typing import Any

import pytest

from rater.citations import XlsxCite
from rater.facts import Fact, Facts
from rater.grids.bands import parse_band
from rater.grids.model import (
    ExceptionRule,
    Grid,
    GridSet,
    MappingRow,
    MappingTable,
    RateCell,
    RateRule,
    Unpublished,
)
from rater.resolve.confidence import Cap

FILE = "raters/acme/test.xlsx"


def cite(cell: str, sheet: str = "Rates") -> XlsxCite:
    return XlsxCite(FILE, sheet, cell)


def facts(verification: str = "verified_both", **values: Any) -> Facts:
    f = Facts()
    for name, value in values.items():
        setattr(
            f,
            name,
            Fact(
                value=value,
                page=1,
                quote=f"{name} {value}",
                verification=verification,
                policy_citation="policy.pdf · page 1",
            ),
        )
    return f


def car(**over: Any) -> Facts:
    base = dict(
        insurer="Acme General Insurance Ltd",
        vehicle_class="private_car",
        policy_type="comprehensive",
        rto="ZZ01",
        fuel="petrol",
        cc=1200,
        manufacture_year=2020,
        policy_start_date=date(2026, 3, 1),
        business_type="renewal",
        od_premium=15000.0,
        ncb=20,
    )
    base.update(over)
    return facts(**{k: v for k, v in base.items() if v is not None})


def rto_map(*pairs: tuple[str, str, str]) -> MappingTable:
    return MappingTable(
        name="RTO → zone",
        source="rto",
        target="zone",
        rows=tuple(MappingRow(key=k, value=v, cite=cite(c, "RTO")) for k, v, c in pairs),
    )


def rule(od: float | None, tp: float | None, row: int, label: str = "", **dims: Any) -> RateRule:
    def band_or_value(name: str, v: Any) -> Any:
        if name in ("cc", "age", "od_premium") and isinstance(v, str):
            band = parse_band(v, {"cc": "cc", "age": "years", "od_premium": "inr"}[name])
            assert band is not None
            return band
        return frozenset(v) if isinstance(v, set) else v

    return RateRule(
        dims=tuple(sorted((k, band_or_value(k, v)) for k, v in dims.items())),
        od=RateCell(od, str(od), cite(f"E{row}")) if od is not None else None,
        tp=RateCell(tp, str(tp), cite(f"F{row}")) if tp is not None else None,
        cite=cite(f"A{row}:F{row}"),
        label=label,
    )


def acme(**over: Any) -> Grid:
    g = dict(
        id="acme/Rates",
        insurer="Acme",
        file=FILE,
        title="Acme private car",
        vehicle_classes=frozenset({"private_car"}),
        policy_types=frozenset({"comprehensive", "satp"}),
        mappings=(rto_map(("ZZ01", "Zone A", "B2"), ("ZZ02", "Zone B", "B3")),),
        rules=(
            rule(12.0, 2.0, 10, "A petrol <1000", zone="Zone A", fuel="petrol", cc="<1000"),
            rule(15.0, 2.5, 11, "A petrol >1000", zone="Zone A", fuel="petrol", cc=">1000"),
            rule(9.0, 1.0, 12, "B petrol all", zone="Zone B", fuel="petrol", cc="All"),
        ),
    )
    g.update(over)
    return Grid(**g)  # type: ignore[arg-type]


def gridset(*grids: Grid) -> GridSet:
    return GridSet(grids=grids or (acme(),), aliases={"Acme": ("acme general",), "Zenith": ("zenith",)})


@pytest.fixture
def unpublished_tp() -> Unpublished:
    return Unpublished("comprehensive", "tp", "grid publishes no TP rate for package policies", cite("H2"))


__all__ = ["Cap", "ExceptionRule", "acme", "car", "cite", "facts", "gridset", "rule", "rto_map"]
