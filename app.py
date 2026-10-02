import json
import time
from pathlib import Path

import streamlit as st

from hiresafe.rules import run_rules

SAMPLES_PATH = Path(__file__).parent / "data" / "sample_messages.json"


def check_stub(text: str) -> dict:
    """Stand-in for hiresafe.pipeline.check(), same output shape. Swap out once B1 lands."""
    start = time.monotonic()
    flags = run_rules(text)
    risk_score = min(100, len(flags) * 18)
    if risk_score >= 50:
        verdict = "likely_scam"
    elif risk_score > 0:
        verdict = "suspicious"
    else:
        verdict = "looks_legit"
    return {
        "verdict": verdict,
        "risk_score": risk_score,
        "flags": flags,
        "similar": [],
        "summary": "Stub pipeline: score is based on rule flags only, no LLM analysis yet.",
        "advice": [
            "Don't pay anything to apply for or accept a job offer.",
            "Verify the role on the company's official careers page.",
            "Report suspected scams at ReportFraud.ftc.gov.",
        ],
        "dropped_quotes": 0,
        "model": "stub",
        "latency_ms": round((time.monotonic() - start) * 1000, 1),
    }


VERDICT_STYLE = {
    "likely_scam": ("\U0001f6a8 Likely Scam", "red"),
    "suspicious": ("⚠️ Suspicious", "orange"),
    "looks_legit": ("✅ Looks Legit", "green"),
}


def load_samples() -> list[dict]:
    if not SAMPLES_PATH.exists():
        return []
    return json.loads(SAMPLES_PATH.read_text())


def main() -> None:
    st.set_page_config(page_title="HireSafe", page_icon="\U0001f6e1️", layout="centered")
    st.title("\U0001f6e1️ HireSafe")
    st.caption("Paste a job posting, recruiter email, or text message to check it for scam red flags.")

    samples = load_samples()
    sample_titles = ["(blank)"] + [s["title"] for s in samples]
    choice = st.selectbox("Try an example", sample_titles)
    default_text = ""
    if choice != "(blank)":
        default_text = next(s["text"] for s in samples if s["title"] == choice)

    text = st.text_area("Message to check", value=default_text, height=220)

    if st.button("Check", type="primary") and text.strip():
        result = check_stub(text)
        label, color = VERDICT_STYLE[result["verdict"]]
        st.markdown(f"### :{color}[{label}] — risk score {result['risk_score']}/100")

        if result["flags"]:
            st.subheader("Red flags")
            for flag in result["flags"]:
                st.markdown(f"- **\"{flag['quote']}\"** — _{flag['category']}_: {flag['explanation']}")
        else:
            st.subheader("Red flags")
            st.write("None found.")

        if result["similar"]:
            st.subheader("Similar known scams")
            for s in result["similar"]:
                st.write(f"- {s}")

        st.subheader("Next steps")
        for tip in result["advice"]:
            st.write(f"- {tip}")

        st.caption(
            f"Model: {result['model']} · {result['latency_ms']} ms · "
            f"{result['dropped_quotes']} unverified quote(s) dropped"
        )
        st.caption("This is guidance, not a guarantee. Always verify independently.")


if __name__ == "__main__":
    main()
