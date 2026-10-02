"""Log each check to HIRESAFE.APP.CHECKS and read today's verdict tally.

Both functions fail gracefully: on an account without the HIRESAFE tables they log a
warning and return an empty result instead of raising.
"""
import json
import logging

from hiresafe.snowflake_client import run_query

log = logging.getLogger(__name__)
VERDICTS = ("likely_scam", "suspicious", "looks_legit")

INSERT_SQL = """
INSERT INTO HIRESAFE.APP.CHECKS (input_text, verdict, risk_score, flags, model, latency_ms)
SELECT %s, %s, %s, PARSE_JSON(%s), %s, %s
"""

TALLY_SQL = """
SELECT verdict, COUNT(*) AS n
FROM HIRESAFE.APP.CHECKS
WHERE created_at >= CURRENT_DATE()
GROUP BY verdict
"""


def log_check(input_text: str, result: dict) -> None:
    """Insert one check. Never raises; failures are logged and ignored."""
    try:
        run_query(INSERT_SQL, (
            input_text,
            result.get("verdict"),
            result.get("risk_score"),
            json.dumps(result.get("flags", [])),
            result.get("model"),
            result.get("latency_ms"),
        ))
    except Exception as e:
        log.warning("log_check failed: %s", e)


def get_tally() -> dict:
    """Today's counts per verdict, e.g. {"likely_scam": 3, "suspicious": 1, "looks_legit": 0}.

    Returns {} if the CHECKS table is unavailable.
    """
    try:
        rows = run_query(TALLY_SQL)
    except Exception as e:
        log.warning("get_tally failed: %s", e)
        return {}
    tally = {v: 0 for v in VERDICTS}
    for row in rows:
        if row["VERDICT"] in tally:
            tally[row["VERDICT"]] = row["N"]
    return tally
