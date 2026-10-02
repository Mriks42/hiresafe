"""The full HireSafe check: rules + LLM analysis + quote verification + similar scams + logging.

Scoring (kept simple so it's easy to explain):
- rule_score = 25 points per distinct rule category matched, capped at 100.
- risk_score = max(llm_score, rule_score): deterministic rules can raise the LLM's score, never lower it.
- verdict: risk_score >= 70 -> likely_scam, >= 35 -> suspicious, otherwise looks_legit.
If the LLM call fails entirely, we fall back to the rule score alone so the user still gets an answer.
"""
import logging
import time

from hiresafe.analysis import analyze
from hiresafe.config import get_settings
from hiresafe.rules import run_rules
from hiresafe.verify import verify_quotes

# Stubs until A pushes store.py / similarity.py; the real modules take over automatically once they exist.
try:
    from hiresafe.store import log_check
except ImportError:
    def log_check(input_text: str, result: dict) -> None:
        return None

try:
    from hiresafe.similarity import similar_scams
except ImportError:
    def similar_scams(text: str, k: int = 3) -> list[dict]:
        return []

log = logging.getLogger(__name__)

POINTS_PER_RULE_CATEGORY = 25
LIKELY_SCAM_THRESHOLD = 70
SUSPICIOUS_THRESHOLD = 35
STANDARD_ADVICE = [
    "Don't pay anything to apply for or accept a job: no fees, equipment, or training costs.",
    "Verify the job on the company's official careers page or by calling their main number.",
    "Report suspected scams at ReportFraud.ftc.gov.",
]


def _verdict(score: int) -> str:
    if score >= LIKELY_SCAM_THRESHOLD:
        return "likely_scam"
    if score >= SUSPICIOUS_THRESHOLD:
        return "suspicious"
    return "looks_legit"


def _merge_flags(rule_flags: list[dict], llm_flags: list[dict]) -> list[dict]:
    """Rule flags first; skip LLM flags that repeat a quote a rule already caught."""
    seen = {f["quote"].lower() for f in rule_flags}
    return rule_flags + [f for f in llm_flags if f["quote"].lower() not in seen]


def _merge_advice(llm_advice: list[str]) -> list[str]:
    seen = {a.lower() for a in STANDARD_ADVICE}
    return STANDARD_ADVICE + [a for a in llm_advice if a.lower() not in seen]


def check(text: str) -> dict:
    start = time.monotonic()

    rule_flags = run_rules(text)
    rule_score = min(100, POINTS_PER_RULE_CATEGORY * len({f["category"] for f in rule_flags}))

    try:
        llm = analyze(text)
        model = get_settings()["model"]
    except Exception as e:  # network, auth, or repeated invalid JSON: degrade to rules only
        log.warning("LLM analysis failed, using rules only: %s", e)
        llm = {"risk_score": 0, "red_flags": [], "advice": [],
               "summary": "AI analysis was unavailable, so this result is based on rule checks only."}
        model = "rules-only"

    flags, dropped = verify_quotes(text, _merge_flags(rule_flags, llm["red_flags"]))
    risk_score = max(llm["risk_score"], rule_score)

    try:
        similar = similar_scams(text, k=3)
    except Exception as e:
        log.warning("similar_scams failed: %s", e)
        similar = []

    result = {
        "verdict": _verdict(risk_score),
        "risk_score": risk_score,
        "flags": flags,
        "similar": similar,
        "summary": llm["summary"],
        "advice": _merge_advice(llm["advice"]),
        "dropped_quotes": dropped,
        "model": model,
        "latency_ms": round((time.monotonic() - start) * 1000),
    }

    try:
        log_check(text, result)
    except Exception as e:  # logging must never block the user
        log.warning("log_check failed: %s", e)
    return result
