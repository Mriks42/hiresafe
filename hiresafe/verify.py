"""Quote verification: keep only flags whose quote appears verbatim in the input."""
import re


def normalize(s: str) -> str:
    """Lowercase, collapse whitespace, and unify curly quotes so matching is forgiving but still verbatim."""
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def _found(quote: str, haystack: str) -> bool:
    """True if quote appears in haystack without starting or ending mid-word ("fee" won't match "coffee")."""
    q = normalize(quote)
    if not q:
        return False
    pattern = re.escape(q)
    if q[0].isalnum():
        pattern = r"(?<!\w)" + pattern
    if q[-1].isalnum():
        pattern += r"(?!\w)"
    return re.search(pattern, haystack) is not None


def verify_quotes(text: str, flags: list[dict]) -> tuple[list[dict], int]:
    """Return (flags whose quote is found in text, number of flags dropped)."""
    haystack = normalize(text)
    kept = [f for f in flags if f.get("quote") and _found(f["quote"], haystack)]
    return kept, len(flags) - len(kept)
