"""Quote verification: keep only flags whose quote appears verbatim in the input."""
import re


def normalize(s: str) -> str:
    """Lowercase, collapse whitespace, and unify curly quotes so matching is forgiving but still verbatim."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def verify_quotes(text: str, flags: list[dict]) -> tuple[list[dict], int]:
    """Return (flags whose quote is found in text, number of flags dropped)."""
    haystack = normalize(text)
    kept = [f for f in flags if f.get("quote") and normalize(f["quote"]) in haystack]
    return kept, len(flags) - len(kept)
