import json

import pytest

from rater.facts import Fact, Facts
from rater.result import RateOut, Result, TraceStep
from rater.switches import Switches

# The challenge page's example result: the keys our output must keep (A4). Values are irrelevant here.
EXAMPLE = {
    "status": "resolved",
    "facts": {"policyType": "comprehensive", "rto": "HR-26", "fuel": "petrol"},
    "rates": {"od": {"applicable": True, "ratePercent": 12}, "tp": {"applicable": True, "ratePercent": 2}},
    "trace": [
        {"decision": "HR-26 maps to Zone A", "policyCitation": "x · page 1", "gridCitation": "g · S!A1"}
    ],
    "confidence": {"level": "high", "reason": "Every required fact and mapping was found"},
}


def _keys(obj: object, prefix: str = "") -> set[str]:
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(prefix + k)
            if k != "facts":
                out |= _keys(v, prefix + k + ".")
    elif isinstance(obj, list) and obj:
        out |= _keys(obj[0], prefix + "[].")
    return out


def _sample_result() -> Result:
    facts = Facts()
    facts.rto = Fact(
        value="HR26", raw="HR-26", page=1, quote="Registration No HR-26", verification="verified_both"
    )
    return Result(
        status="resolved",
        facts=facts,
        rates={
            "od": RateOut(applicable=True, rate_percent=12.0),
            "tp": RateOut(applicable=True, rate_percent=2.0),
        },
        trace=[
            TraceStep(
                step=1, kind="map", decision="d", policy_citation="p · page 1", grid_citation="g · S!A1"
            )
        ],
        confidence={"level": "medium", "reason": "r"},
    )


def test_example_keys_preserved() -> None:
    ours = json.loads(_sample_result().to_json())
    assert _keys(EXAMPLE) <= _keys(ours)


def test_rate_percent_is_a_number_and_null_stays_null() -> None:
    body = json.loads(_sample_result().to_json())
    assert body["rates"]["od"]["ratePercent"] == 12.0
    satp = RateOut.not_applicable("Stand-alone TP policy: OD not applicable")
    dumped = json.loads(json.dumps(satp.dump()))
    assert dumped["applicable"] is False and dumped["ratePercent"] is None


def test_satp_od_shape() -> None:
    od = RateOut.not_applicable("Stand-alone TP policy: OD not applicable").dump()
    assert od["applicable"] is False
    assert od["ratePercent"] is None  # never 0 (A5)
    assert od["reason"]


def test_every_r1_fact_present_even_when_unknown() -> None:
    body = json.loads(_sample_result().to_json())
    for name in (
        "insurer",
        "previousInsurer",
        "businessType",
        "make",
        "model",
        "fuel",
        "rto",
        "cc",
        "manufactureYear",
        "policyType",
        "ncb",
        "odPremium",
        "tpPremium",
        "policyStartDate",
    ):
        assert name in body["facts"], name
    assert body["facts"]["make"]["value"] is None
    assert body["facts"]["make"]["confidence"] == "unknown"


def test_to_json_is_deterministic() -> None:
    assert _sample_result().to_json() == _sample_result().to_json()


def test_switches_defaults_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("GRID_DATE_POLICY", "BROKER_ELIGIBILITY", "LESSER_PERCENT_MEANS"):
        monkeypatch.delenv(k, raising=False)
    s = Switches.from_env()
    assert s.as_dict() == {
        "GRID_DATE_POLICY": "warn",
        "BROKER_ELIGIBILITY": "assume_base",
        "LESSER_PERCENT_MEANS": "points",
    }
    monkeypatch.setenv("GRID_DATE_POLICY", "sometimes")
    with pytest.raises(ValueError):
        Switches.from_env()
