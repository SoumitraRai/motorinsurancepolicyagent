"""Behaviour switches pending Vaatun's reply (intent D1, D2; spec C2). Each is one documented env var."""

import os
from dataclasses import dataclass

_ALLOWED = {
    "GRID_DATE_POLICY": ("warn", "strict"),  # D1
    "BROKER_ELIGIBILITY": ("assume_base", "require_evidence"),  # D2
    "LESSER_PERCENT_MEANS": ("points", "relative"),  # C2: "5% lesser" = 5 points, or 5% of the rate
}


@dataclass(frozen=True)
class Switches:
    grid_date_policy: str = "warn"
    broker_eligibility: str = "assume_base"
    lesser_percent_means: str = "points"

    @classmethod
    def from_env(cls) -> "Switches":
        values = {}
        for name, allowed in _ALLOWED.items():
            value = os.environ.get(name, allowed[0])
            if value not in allowed:
                raise ValueError(f"{name} must be one of {', '.join(allowed)}; got {value!r}")
            values[name.lower()] = value
        return cls(**values)

    def as_dict(self) -> dict[str, str]:
        return {
            "GRID_DATE_POLICY": self.grid_date_policy,
            "BROKER_ELIGIBILITY": self.broker_eligibility,
            "LESSER_PERCENT_MEANS": self.lesser_percent_means,
        }
