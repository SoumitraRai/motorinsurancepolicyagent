"""Insurer names: the canonical name of each supplied grid's insurer, and how policies spell it."""

# Lower-case substrings that identify each insurer in a policy's insurer text.
ALIASES: dict[str, tuple[str, ...]] = {
    "HDFC ERGO": ("hdfc ergo",),
    "Go Digit": ("go digit", "digit general"),
    "Reliance": ("reliance general", "indusind general"),
    "Tata AIG": ("tata aig",),
}


def canonical(text: str, aliases: dict[str, tuple[str, ...]] | None = None) -> str | None:
    low = " ".join(str(text).lower().split())
    for name, needles in (aliases or ALIASES).items():
        if any(n in low for n in needles):
            return name
    return None
