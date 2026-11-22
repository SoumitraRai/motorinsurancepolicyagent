"""Insurer names: the canonical name of each supplied grid's insurer, and how policies spell it."""

# Lower-case substrings that identify each insurer in a policy's insurer text.
ALIASES: dict[str, tuple[str, ...]] = {
    "HDFC ERGO": ("hdfc ergo",),
    "Go Digit": ("go digit", "digit general"),
    "Reliance": ("reliance general", "indusind general"),
    "Tata AIG": ("tata aig",),
}


def _squash(text: str) -> str:
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def canonical(text: str, aliases: dict[str, tuple[str, ...]] | None = None) -> str | None:
    """Spacing-insensitive: OCR often drops spaces ("GoDigitGeneral InsuranceLimited")."""
    squashed = _squash(text)
    for name, needles in (aliases or ALIASES).items():
        if any(_squash(n) in squashed for n in needles):
            return name
    return None
