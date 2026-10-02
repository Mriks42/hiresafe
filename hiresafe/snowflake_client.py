"""Cached Snowflake connection authenticated with a programmatic access token (PAT)."""
from functools import lru_cache

import snowflake.connector

from hiresafe.config import get_settings


@lru_cache(maxsize=1)
def get_conn():
    s = get_settings()
    return snowflake.connector.connect(
        account=s["account"],
        host=s["host"],
        user=s["user"],
        role=s["role"],
        warehouse=s["warehouse"],
        authenticator="PROGRAMMATIC_ACCESS_TOKEN",
        token=s["pat"],
    )


def run_query(sql: str, params=None) -> list[dict]:
    """Run one statement and return rows as dicts (empty list for statements without results)."""
    with get_conn().cursor(snowflake.connector.DictCursor) as cur:
        cur.execute(sql, params)
        return cur.fetchall() if cur.description else []
