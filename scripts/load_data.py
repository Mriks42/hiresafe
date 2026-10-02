"""Load data/fake_job_postings.csv (EMSCAD) into HIRESAFE.APP.JOB_POSTINGS.

Usage:  .venv/bin/python scripts/load_data.py

Some text fields contain Unicode line separators (U+2028 etc.), so we parse with pandas
rather than a line-based loader, then upload with write_pandas and verify the counts.
Re-running replaces the table contents.
"""
import sys
from pathlib import Path

import pandas as pd
from snowflake.connector.pandas_tools import write_pandas

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hiresafe.snowflake_client import get_conn, run_query  # noqa: E402

CSV_PATH = ROOT / "data" / "fake_job_postings.csv"
TABLE = "JOB_POSTINGS"


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.upper() for c in df.columns]
    expected_rows, expected_fraud = len(df), int(df["FRAUDULENT"].sum())
    print(f"CSV: {expected_rows} rows, {expected_fraud} fraudulent")

    conn = get_conn()
    run_query("USE SCHEMA HIRESAFE.APP")
    run_query(f"TRUNCATE TABLE IF EXISTS {TABLE}")
    ok, _, nrows, _ = write_pandas(conn, df, TABLE, database="HIRESAFE", schema="APP",
                                   quote_identifiers=False)
    print(f"write_pandas: success={ok}, rows={nrows}")

    row = run_query(f"SELECT COUNT(*) AS n, SUM(fraudulent) AS fraud FROM {TABLE}")[0]
    print(f"Snowflake: {row['N']} rows, {row['FRAUD']} fraudulent")
    if (row["N"], row["FRAUD"]) != (expected_rows, expected_fraud):
        sys.exit("Count mismatch between CSV and Snowflake.")
    print("Counts match.")


if __name__ == "__main__":
    main()
