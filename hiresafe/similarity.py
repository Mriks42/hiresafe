"""Find known scams similar to a message, using Cortex embeddings stored in KNOWN_SCAMS."""
import logging

from hiresafe.config import get_settings
from hiresafe.snowflake_client import run_query

log = logging.getLogger(__name__)

# e5-base-v2 scores sit high even for unrelated text. Measured top-1 scores on 40 real postings:
# median 0.846; on 40 held-out fraudulent postings: median 0.972. Below this, a "match" is noise.
MIN_SCORE = 0.88

# The query is embedded once in the CTE. Rows identical to the input are skipped so a
# demo example doesn't show up as "similar" to itself.
SIMILAR_SQL = """
WITH q AS (SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768(%s, %s) AS v),
scored AS (
    SELECT k.text, k.source, VECTOR_COSINE_SIMILARITY(k.embedding, q.v) AS score
    FROM HIRESAFE.APP.KNOWN_SCAMS k, q
    WHERE k.text <> %s
)
SELECT text, source, score FROM scored
WHERE score >= %s
ORDER BY score DESC
LIMIT %s
"""


def similar_scams(text: str, k: int = 3) -> list[dict]:
    """Top-k known scams like `text`: [{"text", "source", "score"}]. Returns [] if unavailable."""
    try:
        rows = run_query(SIMILAR_SQL, (get_settings()["embed_model"], text, text, MIN_SCORE, k))
    except Exception as e:
        log.warning("similar_scams failed: %s", e)
        return []
    return [{"text": r["TEXT"], "source": r["SOURCE"], "score": round(float(r["SCORE"]), 3)}
            for r in rows]
