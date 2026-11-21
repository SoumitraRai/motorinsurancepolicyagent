"""OpenRouter chat completions with JSON-schema structured output and page images (OpenAI-compatible API).

Request shape per OpenRouter's docs (checked 2026-11-21): `response_format` `json_schema` with
`strict: true`, `provider.require_parameters: true` so only endpoints that honour the schema are used,
text first then `image_url` parts with base64 PNG data URLs. The reply is `choices[0].message.content`.
"""

import base64
import json
from typing import Any

import httpx

from rater.extraction.normalise import RawExtraction
from rater.extraction.providers.base import ExtractionError, PageInput, validate
from rater.extraction.schema import schema

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM = """You read Indian motor insurance policy documents and extract facts for a broker.
For every field in the schema return: value (as printed), page (1-based page number) and quote.
The quote must be copied verbatim from that page's OCR text given below, and must contain the value.
If a field is not printed in the document, return null for value, page and quote. Never guess,
never infer a value from other fields, never compute a commission rate and never choose a rate grid.
Rules:
- policyType: from the schedule's title and premium sections only; ignore watermarks or background text.
- ncb: the No Claim Bonus percentage applied in this policy's premium; previousNcb: the previous policy's.
- odPremium / tpPremium: the net own-damage and net liability (third-party) premium lines.
- insurer: the insurer issuing this policy; previousInsurer: the insurer of the previous policy, if printed.
- registrationNumber: the vehicle registration number; rto: an RTO code if printed separately.
- addOns: add-on covers listed on the schedule, comma-separated, or "None" if the schedule shows none.
- cpaCover: "Yes" if compulsory personal accident cover for the owner-driver is included, "No" if excluded.
- odTermYears: the number of years of own-damage cover (e.g. 1 for a 1+3 policy)."""


class OpenRouterExtractor:
    name = "openrouter"

    def __init__(
        self, api_key: str, model: str, timeout_s: float = 120, client: httpx.Client | None = None
    ) -> None:
        self.model = model
        self._key = api_key
        self._client = client or httpx.Client(timeout=timeout_s)

    def _body(self, pages: list[PageInput]) -> dict[str, Any]:
        text = "\n\n".join(f"=== Page {p.page} (OCR text) ===\n{p.text}" for p in pages)
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for p in pages:
            if p.image_png:
                url = "data:image/png;base64," + base64.b64encode(p.image_png).decode()
                content.append({"type": "image_url", "image_url": {"url": url}})
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "policy_facts", "strict": True, "schema": schema()},
            },
            "provider": {"require_parameters": True},
            # No sampling parameters: some current models reject them with a 400.
        }

    def extract(self, pages: list[PageInput]) -> RawExtraction:
        try:
            resp = self._client.post(
                ENDPOINT,
                json=self._body(pages),
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "X-OpenRouter-Title": "Brokerage Rate Agent",
                },
            )
        except httpx.TimeoutException as exc:
            raise ExtractionError("timeout waiting for OpenRouter") from exc
        except httpx.HTTPError as exc:
            raise ExtractionError(f"network error ({type(exc).__name__})") from exc
        if resp.status_code != 200:
            try:
                message = resp.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = "no error message"
            raise ExtractionError(f"HTTP {resp.status_code}: {message}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ExtractionError("reply is not JSON") from exc
        return validate(data)
