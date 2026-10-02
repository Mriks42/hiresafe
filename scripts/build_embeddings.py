"""Fill HIRESAFE.APP.KNOWN_SCAMS with embedded scam texts for similarity search.

Usage:  .venv/bin/python scripts/build_embeddings.py

Sources: up to 500 fraudulent EMSCAD postings (already in JOB_POSTINGS) plus the scam
examples in data/sample_messages.json. Embeddings are computed inside Snowflake with
Cortex (model from config: embed_model). Re-running replaces the table contents.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hiresafe.config import get_settings  # noqa: E402
from hiresafe.snowflake_client import run_query  # noqa: E402

SAMPLES_PATH = ROOT / "data" / "sample_messages.json"
MAX_POSTINGS = 500
MAX_CHARS = 2000  # e5-base-v2 reads ~512 tokens; longer text is truncated anyway

# source keeps the job_id so scripts/evaluate.py can exclude these postings from its sample.
# HASH(job_id) gives a fixed, spread-out selection instead of the first 500 ids.
POSTINGS_SQL = f"""
INSERT INTO HIRESAFE.APP.KNOWN_SCAMS (source, text, embedding)
SELECT 'EMSCAD fraudulent posting #' || job_id,
       LEFT(title || '\\n' || description, {MAX_CHARS}),
       SNOWFLAKE.CORTEX.EMBED_TEXT_768(%s, LEFT(title || '\\n' || description, {MAX_CHARS}))
FROM HIRESAFE.APP.JOB_POSTINGS
WHERE fraudulent = 1 AND LENGTH(description) >= 200
ORDER BY HASH(job_id)
LIMIT {MAX_POSTINGS}
"""

SAMPLE_SQL = """
INSERT INTO HIRESAFE.APP.KNOWN_SCAMS (source, text, embedding)
SELECT %s, %s, SNOWFLAKE.CORTEX.EMBED_TEXT_768(%s, %s)
"""


def main() -> None:
    model = get_settings()["embed_model"]
    print(f"Embedding model: {model}")
    run_query("TRUNCATE TABLE IF EXISTS HIRESAFE.APP.KNOWN_SCAMS")

    run_query(POSTINGS_SQL, (model,))

    samples = [s for s in json.loads(SAMPLES_PATH.read_text())
               if s.get("expected_verdict") == "likely_scam"]
    for s in samples:
        run_query(SAMPLE_SQL, (f"Example scam ({s['channel']}): {s['title']}", s["text"], model, s["text"]))

    row = run_query("""SELECT COUNT(*) AS n, COUNT(embedding) AS embedded,
                              COUNT_IF(source LIKE 'EMSCAD%') AS postings
                       FROM HIRESAFE.APP.KNOWN_SCAMS""")[0]
    print(f"KNOWN_SCAMS: {row['N']} rows ({row['POSTINGS']} postings, "
          f"{row['N'] - row['POSTINGS']} examples), {row['EMBEDDED']} embedded")


if __name__ == "__main__":
    main()
