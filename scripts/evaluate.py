"""Evaluate pipeline.check() on a balanced sample of EMSCAD postings from JOB_POSTINGS.

Usage:  .venv/bin/python scripts/evaluate.py [--n 50] [--workers 6] [--seed test1] [--no-similarity] [--no-save]

--no-similarity turns off the similarity part of the risk score (for a before/after comparison
on the same sample); similar scams are still looked up.

- Samples n fraudulent + n real postings from the TEST half of the data (split by HASH(job_id));
  scripts/similarity_cutoffs.py tunes on the other half. --seed picks the sample order, so the
  same seed reruns the same sample. Postings already in KNOWN_SCAMS are excluded.
- Runs check(text, log_result=False) so evaluation doesn't fill today's tally.
- "Predicted scam" = verdict suspicious or likely_scam; strict row counts likely_scam only.
- Unverified-quote rate = dropped quotes / (dropped + LLM quotes kept in the final flags).
  Merged-away LLM flags aren't counted in the denominator, so this slightly overstates the rate.
- Saves one row to EVAL_RESULTS, per-posting details to data/eval_details.csv (gitignored),
  and prints a markdown table for the README.
"""
import argparse
import sys
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hiresafe import pipeline  # noqa: E402
from hiresafe.pipeline import check  # noqa: E402
from hiresafe.snowflake_client import get_conn, run_query  # noqa: E402

DETAILS_PATH = ROOT / "data" / "eval_details.csv"
MIN_DESCRIPTION_CHARS = 200  # same filter for both classes; matches build_embeddings.py
FIELDS = ["title", "location", "salary_range", "company_profile", "description", "requirements", "benefits"]

SAMPLE_SQL = f"""
SELECT job_id, fraudulent, {", ".join(FIELDS)}
FROM HIRESAFE.APP.JOB_POSTINGS
WHERE fraudulent = %s
  AND LENGTH(description) >= {MIN_DESCRIPTION_CHARS}
  AND MOD(ABS(HASH(job_id, 'split')), 2) = 1
  AND job_id NOT IN (SELECT TRY_TO_NUMBER(SPLIT_PART(source, '#', 2))
                     FROM HIRESAFE.APP.KNOWN_SCAMS WHERE source LIKE 'EMSCAD%%')
ORDER BY HASH(job_id, %s)
LIMIT %s
"""

SAVE_SQL = """
INSERT INTO HIRESAFE.APP.EVAL_RESULTS (run_id, n, precision, recall, f1, unverified_quote_rate, notes)
VALUES (%s, %s, %s, %s, %s, %s, %s)
"""


def posting_text(row: dict) -> str:
    """Format a posting the way a user might paste it: labeled, non-empty fields only."""
    parts = []
    for field in FIELDS:
        value = row.get(field.upper())
        if value:
            parts.append(f"{field.replace('_', ' ').title()}: {value}")
    return "\n".join(parts)


def run_one(row: dict) -> dict:
    t0 = time.monotonic()
    try:
        r = check(posting_text(row), log_result=False)
    except Exception as e:  # check() shouldn't raise, but one failure mustn't kill the run
        return {"job_id": row["JOB_ID"], "fraudulent": row["FRAUDULENT"], "error": str(e)[:200]}
    llm_kept = sum(1 for f in r["flags"] if f["source"] in ("llm", "rule+llm"))
    return {
        "job_id": row["JOB_ID"],
        "fraudulent": row["FRAUDULENT"],
        "verdict": r["verdict"],
        "risk_score": r["risk_score"],
        "n_flags": len(r["flags"]),
        "llm_quotes_kept": llm_kept,
        "dropped_quotes": r["dropped_quotes"],
        "model": r["model"],
        "seconds": round(time.monotonic() - t0, 1),
        "error": "",
    }


def metrics(y_true: list[int], y_pred: list[int]) -> dict:
    tp = sum(t and p for t, p in zip(y_true, y_pred))
    fp = sum((not t) and p for t, p in zip(y_true, y_pred))
    fn = sum(t and (not p) for t, p in zip(y_true, y_pred))
    tn = len(y_true) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="postings per class")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", default="test1", help="sample order; change it for a fresh sample")
    ap.add_argument("--no-similarity", action="store_true", help="ignore similarity in the risk score")
    ap.add_argument("--no-save", action="store_true", help="don't write to EVAL_RESULTS")
    args = ap.parse_args()

    if args.no_similarity:
        pipeline.SIMILARITY_CUTOFF = float("inf")  # no match can reach it
    get_conn()  # open the shared connection once, before the threads start
    rows = run_query(SAMPLE_SQL, (1, args.seed, args.n)) + run_query(SAMPLE_SQL, (0, args.seed, args.n))
    print(f"Sample: {sum(r['FRAUDULENT'] for r in rows)} fraudulent + "
          f"{sum(1 - r['FRAUDULENT'] for r in rows)} real postings, {args.workers} workers")

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run_one, rows))
    wall = time.monotonic() - t0

    df = pd.DataFrame(results)
    df.to_csv(DETAILS_PATH, index=False)
    errors = df[df["error"] != ""]
    ok = df[df["error"] == ""]

    y_true = ok["fraudulent"].astype(int).tolist()
    flagged = metrics(y_true, ok["verdict"].isin(["suspicious", "likely_scam"]).astype(int).tolist())
    strict = metrics(y_true, (ok["verdict"] == "likely_scam").astype(int).tolist())
    proposed = int(ok["dropped_quotes"].sum() + ok["llm_quotes_kept"].sum())
    unverified_rate = ok["dropped_quotes"].sum() / proposed if proposed else 0.0
    models = Counter(ok["model"])
    verdicts = pd.crosstab(ok["fraudulent"].map({1: "fraudulent", 0: "real"}), ok["verdict"])

    print(f"\nDone in {wall:.0f}s ({len(ok)} ok, {len(errors)} errors). Models: {dict(models)}")
    print(f"Median latency per check: {ok['seconds'].median():.1f}s\n")
    print(verdicts.to_string(), "\n")

    print("| Positive = | n | Precision | Recall | F1 | TP | FP | FN | TN |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, m in [("suspicious or likely_scam", flagged), ("likely_scam only", strict)]:
        print(f"| {name} | {len(ok)} | {m['precision']:.2f} | {m['recall']:.2f} | {m['f1']:.2f} "
              f"| {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} |")
    print(f"\nUnverified-quote rate: {unverified_rate:.1%} "
          f"({int(ok['dropped_quotes'].sum())} of {proposed} LLM quotes dropped)")
    print(f"Per-posting details: {DETAILS_PATH.relative_to(ROOT)}")

    if args.no_save:
        return
    run_id = uuid.uuid4().hex[:8]
    notes = (f"EMSCAD balanced {args.n}+{args.n}, test half, seed={args.seed}, similarity_score={'off' if args.no_similarity else 'on'}; positive=suspicious|likely_scam; "
             f"strict likely_scam P={strict['precision']:.2f} R={strict['recall']:.2f} F1={strict['f1']:.2f}; "
             f"models={dict(models)}; errors={len(errors)}; desc>={MIN_DESCRIPTION_CHARS} chars")
    run_query(SAVE_SQL, (run_id, len(ok), flagged["precision"], flagged["recall"], flagged["f1"],
                         float(unverified_rate), notes))
    print(f"Saved to EVAL_RESULTS as run_id {run_id}")


if __name__ == "__main__":
    main()
