"""Canonical vehicle make names. Grids abbreviate or misspell makes ("Volks", "Citrone"); policies print
the full name ("MARUTI SUZUKI"). Both sides go through `canonical_make` so they compare equal.

Only spelling and abbreviation aliases live here, never a make-to-segment judgement (README assumption).
"""

_ALIASES = {
    "VOLKS": "VOLKSWAGEN",
    "VW": "VOLKSWAGEN",
    "CITRONE": "CITROEN",
    "MARUTISUZUKI": "MARUTI",
    "MARUTI SUZUKI": "MARUTI",
    "MERCEDES": "MERCEDES BENZ",
    "MERCEDESBENZ": "MERCEDES BENZ",
    "MAHINDRA AND MAHINDRA": "MAHINDRA",
    "M&M": "MAHINDRA",
    "TATA MOTORS": "TATA",
    "LANDROVER": "LAND ROVER",
    "ROLLSROYCE": "ROLLS ROYCE",
}


def canonical_make(text: str) -> str:
    t = " ".join(str(text).upper().replace("-", " ").split())
    if t in _ALIASES:
        return _ALIASES[t]
    squashed = t.replace(" ", "")
    return _ALIASES.get(squashed, t)
