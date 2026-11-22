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
    "HERO": "HERO MOTOCORP",
    "HEROMOTOCORP": "HERO MOTOCORP",
    "HMC": "HERO MOTOCORP",
    "RE": "ROYAL ENFIELD",
    "ROYALENFIELD": "ROYAL ENFIELD",
}


def canonical_make(text: str) -> str:
    t = " ".join(str(text).upper().replace("-", " ").split())
    if t in _ALIASES:
        return _ALIASES[t]
    squashed = t.replace(" ", "")
    return _ALIASES.get(squashed, t)


# Known makes, used only to split a make glued to its model by OCR ("RENAULTKWID" → "RENAULT").
KNOWN_MAKES = (
    "MARUTI",
    "HYUNDAI",
    "TATA",
    "MAHINDRA",
    "KIA",
    "TOYOTA",
    "HONDA",
    "RENAULT",
    "NISSAN",
    "DATSUN",
    "FORD",
    "VOLKSWAGEN",
    "SKODA",
    "MG",
    "JEEP",
    "BMW",
    "AUDI",
    "MERCEDES BENZ",
    "VOLVO",
    "JAGUAR",
    "LAND ROVER",
    "PORSCHE",
    "LEXUS",
    "CITROEN",
    "BYD",
    "TESLA",
    "FIAT",
    "CHEVROLET",
    "ISUZU",
    "FORCE",
    "MINI",
    "BAJAJ",
    "HERO",
    "TVS",
    "YAMAHA",
    "SUZUKI",
    "ROYAL ENFIELD",
    "KTM",
    "ASHOK LEYLAND",
    "EICHER",
    "JAWA",
    "ATHER",
    "OLA",
    "PIAGGIO",
    "VESPA",
    "APRILIA",
    "HARLEY DAVIDSON",
    "KAWASAKI",
    "BENELLI",
    "TRIUMPH",
    "DUCATI",
)


def split_make(text: str) -> str:
    """The make, if `text` starts with a known make glued to more letters; otherwise `text` unchanged."""
    squashed = "".join(str(text).upper().split())
    for make in sorted(KNOWN_MAKES, key=len, reverse=True):
        key = make.replace(" ", "")
        if squashed.startswith(key) and squashed != key:
            return make
    return text
