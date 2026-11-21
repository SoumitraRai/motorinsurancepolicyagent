"""The extraction JSON schema (spec SR5): per field a value, its 1-based page and a verbatim quote."""

from typing import Any

from rater.extraction.normalise import FIELDS

FIELD_NAMES: tuple[str, ...] = tuple(FIELDS)

_NULLABLE = {"string": ["string", "null"], "integer": ["integer", "null"]}


def schema() -> dict[str, Any]:
    field = {
        "type": "object",
        "properties": {
            "value": {"type": _NULLABLE["string"]},
            "page": {"type": _NULLABLE["integer"]},
            "quote": {"type": _NULLABLE["string"]},
        },
        "required": ["value", "page", "quote"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {name: field for name in FIELD_NAMES},
        "required": list(FIELD_NAMES),
        "additionalProperties": False,
    }
