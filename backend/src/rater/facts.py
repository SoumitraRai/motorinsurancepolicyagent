"""Policy facts (spec SR5): every R1 fact is always present; unknown stays unknown, never guessed."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

Verification = Literal[
    "text_layer",  # quote found in the PDF's own text layer
    "verified_both",  # quote found in both OCR engines' text
    "verified_one",  # quote found in one OCR engine's text
    "unverified",  # value given but quote not found on the cited page
    "not_found",  # no value
    "reviewer_supplied",  # supplied by the reviewer through /clarify (SR25)
    "derived",  # computed by code from other facts (e.g. business type, SR8)
]
Level = Literal["high", "medium", "low", "unknown"]


class Fuel(StrEnum):
    PETROL = "petrol"
    DIESEL = "diesel"
    CNG = "cng"
    LPG = "lpg"
    ELECTRIC = "electric"
    HYBRID = "hybrid"


class PolicyType(StrEnum):
    COMPREHENSIVE = "comprehensive"  # package: OD + TP
    SAOD = "saod"  # stand-alone own damage
    SATP = "satp"  # stand-alone third party


class BusinessType(StrEnum):
    NEW = "new"
    RENEWAL = "renewal"
    ROLLOVER = "rollover"


class VehicleClass(StrEnum):
    PRIVATE_CAR = "private_car"
    TWO_WHEELER = "two_wheeler"
    SCOOTER = "scooter"
    GCV = "gcv"
    PCV_TAXI = "pcv_taxi"
    PCV_3W = "pcv_3w"
    SCHOOL_BUS = "school_bus"
    STAFF_BUS = "staff_bus"
    MISC_D = "misc_d"
    TRACTOR = "tractor"


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, validate_assignment=True)


class Fact(_Model):
    value: Any = None
    raw: str | None = None
    page: int | None = None
    quote: str | None = None
    verification: Verification = "not_found"
    confidence: Level = "unknown"
    policy_citation: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _level(self) -> "Fact":
        from rater.resolve.confidence import fact_level

        object.__setattr__(self, "confidence", fact_level(self))
        return self

    @property
    def known(self) -> bool:
        return self.value is not None


def _unknown() -> Fact:
    return Fact()


class Facts(_Model):
    """R1 facts plus the extra dimensions some grids use (vehicle class, GVW, seating)."""

    insurer: Fact = Field(default_factory=_unknown)
    previous_insurer: Fact = Field(default_factory=_unknown)
    business_type: Fact = Field(default_factory=_unknown)
    vehicle_class: Fact = Field(default_factory=_unknown)
    make: Fact = Field(default_factory=_unknown)
    model: Fact = Field(default_factory=_unknown)
    fuel: Fact = Field(default_factory=_unknown)
    rto: Fact = Field(default_factory=_unknown)
    rto_location: Fact = Field(default_factory=_unknown)
    cc: Fact = Field(default_factory=_unknown)
    manufacture_year: Fact = Field(default_factory=_unknown)
    registration_year: Fact = Field(default_factory=_unknown)
    policy_type: Fact = Field(default_factory=_unknown)
    ncb: Fact = Field(default_factory=_unknown)
    previous_ncb: Fact = Field(default_factory=_unknown)
    od_premium: Fact = Field(default_factory=_unknown)
    tp_premium: Fact = Field(default_factory=_unknown)
    net_premium: Fact = Field(default_factory=_unknown)
    policy_start_date: Fact = Field(default_factory=_unknown)
    issue_date: Fact = Field(default_factory=_unknown)
    gvw: Fact = Field(default_factory=_unknown)
    seating_capacity: Fact = Field(default_factory=_unknown)
    segment: Fact = Field(default_factory=_unknown)

    def get(self, name: str) -> Fact:
        """Fact by snake_case or camelCase name."""
        attr = name if name in type(self).model_fields else _snake(name)
        return getattr(self, attr)  # type: ignore[no-any-return]

    def value(self, name: str) -> Any:
        return self.get(name).value


def _snake(name: str) -> str:
    return "".join("_" + c.lower() if c.isupper() else c for c in name)
