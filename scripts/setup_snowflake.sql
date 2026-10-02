-- HireSafe Snowflake objects. Safe to re-run (IF NOT EXISTS everywhere).
CREATE DATABASE IF NOT EXISTS HIRESAFE;
CREATE SCHEMA IF NOT EXISTS HIRESAFE.APP;
USE SCHEMA HIRESAFE.APP;

-- EMSCAD dataset (data/fake_job_postings.csv), loaded by scripts/load_data.py
CREATE TABLE IF NOT EXISTS JOB_POSTINGS (
    job_id              NUMBER,
    title               STRING,
    location            STRING,
    department          STRING,
    salary_range        STRING,
    company_profile     STRING,
    description         STRING,
    requirements        STRING,
    benefits            STRING,
    telecommuting       NUMBER(1),
    has_company_logo    NUMBER(1),
    has_questions       NUMBER(1),
    employment_type     STRING,
    required_experience STRING,
    required_education  STRING,
    industry            STRING,
    function            STRING,
    fraudulent          NUMBER(1)
);

-- Known scam texts for similarity search; embedding filled by scripts/build_embeddings.py
CREATE TABLE IF NOT EXISTS KNOWN_SCAMS (
    id        NUMBER AUTOINCREMENT,
    source    STRING,
    text      STRING,
    embedding VECTOR(FLOAT, 768)
);

-- One row per user check (logged by hiresafe/store.py)
CREATE TABLE IF NOT EXISTS CHECKS (
    id          NUMBER AUTOINCREMENT,
    created_at  TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    input_text  STRING,
    verdict     STRING,
    risk_score  NUMBER,
    flags       VARIANT,
    model       STRING,
    latency_ms  NUMBER
);

-- One row per evaluation run (scripts/evaluate.py)
CREATE TABLE IF NOT EXISTS EVAL_RESULTS (
    run_id                STRING,
    created_at            TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    n                     NUMBER,
    precision             FLOAT,
    recall                FLOAT,
    f1                    FLOAT,
    unverified_quote_rate FLOAT,
    notes                 STRING
);
