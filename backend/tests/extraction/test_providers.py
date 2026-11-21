import ast
import json
from pathlib import Path

import httpx
import pytest

from rater.extraction.providers.base import (
    ExtractionError,
    PageInput,
    choose_extractor,
    extract_with_fallback,
)
from rater.extraction.providers.openrouter import ENDPOINT, OpenRouterExtractor
from rater.extraction.providers.rules import RulesExtractor
from rater.extraction.schema import FIELD_NAMES, schema

SRC = Path(__file__).resolve().parents[2] / "src" / "rater"
PAGES = [
    PageInput(page=1, text="Policy Schedule\nCubic Capacity 1197\nFuel Type Petrol", image_png=b"\x89PNGfake")
]


def ok_payload(**values: str) -> dict:  # type: ignore[type-arg]
    fields = {n: {"value": None, "page": None, "quote": None} for n in FIELD_NAMES}
    for k, v in values.items():
        fields[k] = {"value": v, "page": 1, "quote": f"{k} {v}"}
    return {"choices": [{"message": {"role": "assistant", "content": json.dumps(fields)}}]}


def extractor(handler) -> OpenRouterExtractor:  # type: ignore[no-untyped-def]
    return OpenRouterExtractor(
        "sk-test", "vendor/vision-model", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_schema_is_strict_and_covers_every_field() -> None:
    s = schema()
    assert s["additionalProperties"] is False and set(s["required"]) == set(FIELD_NAMES)
    for name in FIELD_NAMES:
        prop = s["properties"][name]
        assert prop["additionalProperties"] is False and set(prop["required"]) == {"value", "page", "quote"}


def test_openrouter_request_shape() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ok_payload(cc="1197"))

    extractor(handler).extract(PAGES)
    (req,) = seen
    assert str(req.url) == ENDPOINT and req.headers["authorization"] == "Bearer sk-test"
    body = json.loads(req.content)
    assert body["model"] == "vendor/vision-model"
    rf = body["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["schema"] == schema()
    assert body["provider"] == {"require_parameters": True}
    user = body["messages"][-1]["content"]
    assert (
        user[0]["type"] == "text" and "Cubic Capacity 1197" in user[0]["text"]
    )  # page-tagged OCR text first
    assert user[1]["type"] == "image_url" and user[1]["image_url"]["url"].startswith("data:image/png;base64,")
    system = body["messages"][0]["content"].lower()
    assert "verbatim" in system and "never" in system and "rate" in system


def test_openrouter_response_parsed() -> None:
    raw = extractor(lambda r: httpx.Response(200, json=ok_payload(cc="1197", fuel="Petrol"))).extract(PAGES)
    assert raw["cc"].value == "1197" and raw["cc"].page == 1 and raw["cc"].quote == "cc 1197"
    assert raw["make"].value is None


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500, json={"error": {"code": 500, "message": "boom"}}),
        lambda r: httpx.Response(429, json={"error": {"code": 429, "message": "Rate limit exceeded"}}),
        lambda r: httpx.Response(402, json={"error": {"code": 402, "message": "Insufficient credits"}}),
        lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}),
        lambda r: httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"cc": 5})}}]}),
    ],
)
def test_openrouter_error_falls_back_to_rules(handler) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ExtractionError):
        extractor(handler).extract(PAGES)
    raw, used, note = extract_with_fallback(PAGES, extractor(handler), RulesExtractor())
    assert used == "rules" and note and raw["cc"].value == "1197"


def test_timeout_falls_back() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    _, used, note = extract_with_fallback(PAGES, extractor(handler), RulesExtractor())
    assert used == "rules" and "timeout" in (note or "").lower()


def test_rules_extracts_from_synthetic_rows() -> None:
    pages = [
        PageInput(
            1,
            "ACME GENERAL INSURANCE COMPANY LIMITED\nPrivate Car Package Policy Schedule\n"
            "Registration No ZZ-07-CD-1234\nRTO Location ZZTOWN\nCubic Capacity 1197\n"
            "Fuel Type Diesel\nYear of Manufacture 2019\nLess: No Claim Bonus (20%) 400",
            None,
        ),
        PageInput(
            2,
            "Net Own Damage Premium (a) 4,100\nNet Liability Premium (b) 3,416\n"
            "Period of Insurance From 01/04/2026 to 31/03/2027",
            None,
        ),
    ]
    raw = RulesExtractor().extract(pages)
    assert raw["registrationNumber"].value.replace(" ", "") == "ZZ-07-CD-1234"
    assert raw["cc"].value == "1197" and raw["cc"].page == 1 and "Cubic Capacity 1197" in raw["cc"].quote
    assert raw["fuel"].value.lower() == "diesel"
    assert raw["ncb"].value == "20" and raw["odPremium"].value == "4,100" and raw["odPremium"].page == 2
    assert raw["policyType"].value.lower().startswith("private car package")
    assert raw["insurer"].value.startswith("ACME GENERAL INSURANCE")
    assert raw["policyStartDate"].value == "01/04/2026"


def test_rules_unknown_label_gives_null() -> None:
    raw = RulesExtractor().extract([PageInput(1, "Nothing useful here", None)])
    assert all(raw[n].value is None for n in FIELD_NAMES)


def test_choose_extractor(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("OPENROUTER_API_KEY", "EXTRACTION_MODEL", "EXTRACTION_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    assert isinstance(choose_extractor(), RulesExtractor)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk")
    assert isinstance(choose_extractor(), RulesExtractor)  # no model chosen yet: never guess one
    monkeypatch.setenv("EXTRACTION_MODEL", "vendor/model")
    assert isinstance(choose_extractor(), OpenRouterExtractor)
    monkeypatch.setenv("EXTRACTION_PROVIDER", "rules")
    assert isinstance(choose_extractor(), RulesExtractor)


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_only_providers_make_llm_calls() -> None:
    allowed_http = ("extraction/providers/", "storage/", "api/")
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        mods = _imports(path)
        assert not any(m.split(".")[0] in {"openai", "anthropic"} for m in mods), rel
        if any(m.split(".")[0] == "httpx" for m in mods):
            assert rel.startswith(allowed_http), rel
        if rel.startswith(("grids/", "resolve/")):
            assert not any("extraction" in m for m in mods), rel
