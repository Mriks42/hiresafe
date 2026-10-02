import html
import json
import re
from pathlib import Path

import streamlit as st

from hiresafe.pipeline import SIMILARITY_CUTOFF, check, matches_known_scam
from hiresafe.store import get_tally

SAMPLES_PATH = Path(__file__).parent / "data" / "sample_messages.json"
PASTE_OWN = "✍️ Paste my own message"

VERDICT_STYLE = {  # label, background, text color
    "likely_scam": ("🚨 Likely Scam", "#fde2e1", "#b42318"),
    "suspicious": ("⚠️ Suspicious", "#fef3c7", "#92400e"),
    "looks_legit": ("✅ Looks Legit", "#dcfce7", "#166534"),
}
HIGHLIGHT_STYLE = "background:#fde68a;color:#111;border-radius:3px;padding:0 2px;"
DISCLAIMER = ("HireSafe gives guidance, not a guarantee. A message can look legit and still be a scam, "
              "so always verify independently before sharing personal info or money.")


def load_samples() -> list[dict]:
    if not SAMPLES_PATH.exists():
        return []
    return json.loads(SAMPLES_PATH.read_text())


def md(s: str) -> str:
    """Escape '$' so Streamlit markdown doesn't render dollar amounts as LaTeX."""
    return s.replace("$", "\\$")


def _quote_pattern(quote: str) -> str:
    """Regex for a quote that tolerates whitespace and curly-quote differences, like verify_quotes."""
    parts = []
    for word in quote.split():
        escaped = re.escape(word)
        escaped = escaped.replace("'", "['‘’]").replace('"', '["“”]')
        parts.append(escaped)
    return r"\s+".join(parts)


def highlight(text: str, flags: list[dict]) -> str:
    """Return the input as HTML with every flagged quote wrapped in a <mark>."""
    spans = []
    for f in flags:
        for m in re.finditer(_quote_pattern(f["quote"]), text, re.IGNORECASE):
            spans.append((m.start(), m.end(), f["category"]))
    spans.sort()

    out, pos = [], 0
    for start, end, category in spans:
        if start < pos:  # overlaps a span we already marked
            continue
        out.append(html.escape(text[pos:start]))
        out.append(f'<mark style="{HIGHLIGHT_STYLE}" title="{html.escape(category)}">'
                   f"{html.escape(text[start:end])}</mark>")
        pos = end
    out.append(html.escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


def render_verdict(result: dict) -> None:
    label, bg, fg = VERDICT_STYLE[result["verdict"]]
    st.html(
        f'<div style="background:{bg};color:{fg};border-radius:12px;padding:18px 24px;'
        f'display:flex;justify-content:space-between;align-items:center;font-family:sans-serif;">'
        f'<span style="font-size:2rem;font-weight:700;">{label}</span>'
        f'<span style="font-size:1.4rem;font-weight:600;">Risk score {result["risk_score"]}/100</span>'
        f"</div>"
    )
    if result["summary"]:
        st.markdown(md(result["summary"]))
    if matches_known_scam(result["similar"]):
        st.markdown(f"🔁 **Closely matches a known scam** (similarity {result['similar'][0]['score']:.2f}). "
                    "See below.")


def render_result(text: str, result: dict) -> None:
    render_verdict(result)

    st.subheader("Your message")
    st.html(
        '<div style="border:1px solid #d0d5dd;border-radius:8px;padding:14px 16px;'
        'line-height:1.6;font-family:sans-serif;font-size:1.05rem;">'
        f"{highlight(text, result['flags'])}</div>"
    )

    st.subheader(f"Red flags ({len(result['flags'])})")
    if result["flags"]:
        for f in result["flags"]:
            category = f["category"].replace("_", " ")
            st.markdown(md(f'- **"{f["quote"]}"** · _{category}_  \n  {f["explanation"]}'))
    else:
        st.write("No red flags found.")

    # Only show matches strong enough to count in the score; genuine postings can reach ~0.90.
    close_matches = [s for s in result["similar"] if s["score"] >= SIMILARITY_CUTOFF]
    if close_matches:
        st.subheader("Similar known scams")
        for s in close_matches:
            preview = s["text"][:300] + ("…" if len(s["text"]) > 300 else "")
            with st.expander(md(f"{s['source']} · similarity {s['score']:.2f}")):
                st.write(md(preview))

    st.subheader("Next steps")
    for tip in result["advice"]:
        st.markdown(md(f"- {tip}"))

    st.caption(
        f"Model: {result['model']} (open-weight, via Snowflake Cortex) · {result['latency_ms']} ms · "
        f"{result['dropped_quotes']} unverified AI quote(s) dropped"
    )
    st.info(DISCLAIMER)


def render_sidebar() -> None:
    st.sidebar.header("Today on HireSafe")
    try:
        tally = get_tally()
    except Exception:
        tally = {}
    if not tally:
        st.sidebar.caption("Tally unavailable.")
        return
    st.sidebar.metric("🚨 Likely scams", tally.get("likely_scam", 0))
    st.sidebar.metric("⚠️ Suspicious", tally.get("suspicious", 0))
    st.sidebar.metric("✅ Looks legit", tally.get("looks_legit", 0))
    st.sidebar.caption("Counts only; we never show other people's messages.")


def main() -> None:
    st.set_page_config(page_title="HireSafe", page_icon="🛡️", layout="centered")
    st.title("🛡️ HireSafe")
    st.caption("Paste a job posting, recruiter email, or text message to check it for scam red flags.")

    samples = load_samples()
    sample_titles = [PASTE_OWN] + [s["title"] for s in samples]
    choice = st.selectbox("Paste your own message, or load an example", sample_titles)
    default_text = ""
    if choice != PASTE_OWN:
        default_text = next(s["text"] for s in samples if s["title"] == choice)

    text = st.text_area(
        "Message to check", value=default_text, height=260,
        placeholder="Paste a job description, recruiter email, LinkedIn message, or text here…",
    )

    clicked = st.button("Check", type="primary")
    if clicked and not text.strip():
        st.warning("Paste a message above first.")
    if clicked and text.strip():
        with st.spinner("Checking with Llama 3.1 on Snowflake Cortex…"):
            result = check(text)
        render_result(text, result)

    render_sidebar()  # after the check, so the tally includes it


if __name__ == "__main__":
    main()
