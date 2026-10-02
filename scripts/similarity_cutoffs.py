"""Measure how often real vs fraudulent postings have a close match in KNOWN_SCAMS.

Usage:  .venv/bin/python scripts/similarity_cutoffs.py [--real 300]

Used to choose a similarity cutoff for the risk score. Runs only on the TUNING half of the
postings (split by HASH(job_id)); scripts/evaluate.py samples from the other half, so the
cutoff is never tested on the data it was picked from. Postings already in KNOWN_SCAMS are
excluded. Text is formatted exactly like evaluate.py's posting_text(), so scores match what
similar_scams() sees during evaluation.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hiresafe.config import get_settings  # noqa: E402
from hiresafe.snowflake_client import run_query  # noqa: E402

CUTOFFS = [0.88, 0.90, 0.93, 0.95, 0.99]

# Same labels and order as evaluate.posting_text(); ARRAY_CONSTRUCT_COMPACT drops NULL fields.
TOP_SCORE_SQL = """
WITH pool AS (
    SELECT job_id, fraudulent,
           ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(
               'Title: ' || title, 'Location: ' || location, 'Salary Range: ' || salary_range,
               'Company Profile: ' || company_profile, 'Description: ' || description,
               'Requirements: ' || requirements, 'Benefits: ' || benefits), '\\n') AS text
    FROM HIRESAFE.APP.JOB_POSTINGS
    WHERE LENGTH(description) >= 200
      AND MOD(ABS(HASH(job_id, 'split')), 2) = 0
      AND job_id NOT IN (SELECT TRY_TO_NUMBER(SPLIT_PART(source, '#', 2))
                         FROM HIRESAFE.APP.KNOWN_SCAMS WHERE source LIKE 'EMSCAD%%')
),
picked AS (
    SELECT * FROM pool WHERE fraudulent = 1
    UNION ALL
    (SELECT * FROM pool WHERE fraudulent = 0 ORDER BY HASH(job_id, 'tune') LIMIT %s)
),
embedded AS (
    SELECT job_id, fraudulent, text, SNOWFLAKE.CORTEX.EMBED_TEXT_768(%s, text) AS v FROM picked
)
SELECT e.job_id, e.fraudulent, MAX(VECTOR_COSINE_SIMILARITY(k.embedding, e.v)) AS top
FROM embedded e, HIRESAFE.APP.KNOWN_SCAMS k
WHERE k.text <> e.text
GROUP BY e.job_id, e.fraudulent
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", type=int, default=300, help="real postings to sample")
    args = ap.parse_args()

    rows = run_query(TOP_SCORE_SQL, (args.real, get_settings()["embed_model"]))
    groups = {"real": sorted(r["TOP"] for r in rows if r["FRAUDULENT"] == 0),
              "fraudulent": sorted(r["TOP"] for r in rows if r["FRAUDULENT"] == 1)}

    print("Tuning half only (evaluate.py uses the other half). Top-1 similarity to KNOWN_SCAMS.\n")
    print("| Top score ≥ | " + " | ".join(f"{name} (n={len(v)})" for name, v in groups.items()) + " |")
    print("|---|---|---|")
    for c in CUTOFFS:
        cells = []
        for v in groups.values():
            hit = sum(s >= c for s in v)
            cells.append(f"{hit / len(v):.1%} ({hit})")
        print(f"| {c:.2f} | " + " | ".join(cells) + " |")
    for name, v in groups.items():
        print(f"\n{name}: median {v[len(v) // 2]:.3f}, max {v[-1]:.3f}")


if __name__ == "__main__":
    main()
