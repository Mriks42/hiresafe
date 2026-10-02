# HireSafe — project context for Claude Code (2-person team)

## Team and ownership (read first)
Two people build this in parallel. Each runs their own Claude Code session on their own laptop,
and both sessions read this file.

- **Person A — Mrigank** (GitHub: Mriks42): Snowflake, data, LLM client, logging, similarity search,
  evaluation, and the stretch investigator agent.
- **Person B — [PARTNER NAME]**: scam rules, the analysis prompt, quote verification, the pipeline,
  the Streamlit UI, demo data, the CLI, the Agent Skill, and the README draft.

At the start of a session, the human says which person they are. **Only create or edit files owned
by that person.** If a change is needed in the other person's file, don't make it; write the exact
change as a short note for the human to pass on.

| File | Owner |
|---|---|
| `hiresafe/config.py`, `hiresafe/snowflake_client.py`, `hiresafe/llm.py`, `hiresafe/store.py`, `hiresafe/similarity.py`, `hiresafe/agent.py` | A |
| `scripts/setup_snowflake.sql`, `scripts/load_data.py`, `scripts/build_embeddings.py`, `scripts/evaluate.py` | A |
| `hiresafe/rules.py`, `hiresafe/analysis.py`, `hiresafe/verify.py`, `hiresafe/pipeline.py`, `app.py` | B |
| `scripts/check.py`, `data/sample_messages.json`, `skills/hiresafe-check/SKILL.md`, `README.md` (A adds the eval section) | B |
| `requirements.txt`, `.gitignore`, `CLAUDE.md`, `hiresafe/__init__.py` | Shared: tell the other person before changing |

## Interface contract
Both sides code against these signatures. Don't change one without telling the other person.
Until a dependency exists, use a small stub with the same signature (for example, `similar_scams`
returning `[]`) and delete the stub once the real version is pushed.

```python
# hiresafe/config.py (A)
def get_settings() -> dict: ...
    # reads .streamlit/secrets.toml, section [snowflake]: account, host, user, role, warehouse, pat, model

# hiresafe/llm.py (A)
def chat(messages: list[dict], model: str | None = None,
         temperature: float = 0.0, max_tokens: int = 1024) -> str: ...

# hiresafe/snowflake_client.py (A)
def get_conn(): ...                                   # cached connection
def run_query(sql: str, params=None) -> list[dict]: ...

# hiresafe/store.py (A)
def log_check(input_text: str, result: dict) -> None: ...  # never raises; failures are logged and ignored
def get_tally() -> dict: ...  # today's counts: {"likely_scam": n, "suspicious": n, "looks_legit": n}

# hiresafe/similarity.py (A)
def similar_scams(text: str, k: int = 3) -> list[dict]: ...  # [{"text", "source", "score"}]; [] if unavailable

# hiresafe/rules.py (B)
def run_rules(text: str) -> list[dict]: ...
    # flags: {"quote", "category", "explanation", "source": "rule"}

# hiresafe/analysis.py (B)
def analyze(text: str) -> dict: ...
    # {"verdict", "risk_score", "red_flags": [{"quote", "category", "explanation", "source": "llm"}],
    #  "summary", "advice": []}

# hiresafe/verify.py (B)
def verify_quotes(text: str, flags: list[dict]) -> tuple[list[dict], int]: ...  # (kept, dropped_count)

# hiresafe/pipeline.py (B)
def check(text: str) -> dict: ...
    # {"verdict", "risk_score", "flags", "similar", "summary", "advice",
    #  "dropped_quotes", "model", "latency_ms"}
```

## What we're building
HireSafe checks a job posting, recruiter email, or text message and tells the user whether it's
likely a scam. It's built at a 4-hour hackathon (Hacktoberfest Hack Day Tempe x sunhacks, MLH).
Hacking runs 11:20 AM – 3:30 PM. Prefer simple and working over clever. Every push must leave
`main` runnable.

Target prizes:
- **Best Use of Snowflake**: data, search, and logging live in Snowflake; LLM calls go through Snowflake Cortex.
- **Best Open-Source AI Project**: an open-weight model is the core of the analysis; the repo is public
  with an Apache-2.0 license. Bonus: an Agent Skill that follows the Agent Skills open standard.

## Output for each check
1. Verdict: `likely_scam` / `suspicious` / `looks_legit`, plus a 0–100 risk score.
2. Red flags, each with the **exact quoted phrase** from the input, a category, and a plain-English explanation.
3. Similar known scams (top 3) from Snowflake, if available.
4. Next steps: don't pay anything, verify via the company's official careers page, report at ReportFraud.ftc.gov.
5. A short disclaimer: this is guidance, not a guarantee.

## Stack
- Python 3.14 in `.venv` (activate with `source .venv/bin/activate`), Streamlit, snowflake-connector-python,
  pandas. Use `pyarrow<24` (newer versions trigger connector warnings). Record every package in `requirements.txt`.
- LLM: Meta Llama 3.1 70B (open-weight) through Snowflake Cortex. It runs on Snowflake's servers, not locally.

## Snowflake facts (verified on this account)
- **Main account (A's):** account identifier `GWIQZLO-TEB18647`, host `gwiqzlo-teb18647.snowflakecomputing.com`,
  user `MRIKS42`, warehouse `COMPUTE_WH` (X-Small), role `ACCOUNTADMIN`. All HIRESAFE tables live here,
  and the final demo and evaluation run against this account (on A's laptop).
- **B uses their own separate Snowflake trial account during development**, mainly for LLM calls.
  Never hardcode the account or host anywhere: always read them from `secrets.toml`, so the same code
  works on both accounts.
- On B's account the HIRESAFE tables may not exist, so `log_check`, `get_tally`, and `similar_scams` must
  fail gracefully (log a warning and return an empty result) instead of crashing the pipeline or the UI.
- LLM endpoint (OpenAI-compatible): `https://<host from secrets>/api/v2/cortex/v1/chat/completions`
  with header `Authorization: Bearer <PAT>`. The OpenAI Python SDK also works with
  `base_url="https://<host from secrets>/api/v2/cortex/v1"`.
- **Model: `llama3.1-70b`** (confirmed working). Fallback: `llama3.1-8b`. Keep the model name in config only.
- These models FAIL on this account (legacy or deprecated): `mistral-large2`, `snowflake-llama-3.3-70b`,
  `llama4-maverick`. Don't use them.
- Cortex does NOT support built-in tool calling for open-weight models. Never send a `tools` parameter.
  Get structured output by asking for JSON in the prompt and validating it.
- PATs need a network-policy bypass, granted in Snowsight for up to 24 hours. If calls suddenly fail
  with an auth error, the bypass probably expired; tell the human to re-grant it.
- For the Python connector, check the current docs for PAT authentication (PAT as password, or
  `authenticator="PROGRAMMATIC_ACCESS_TOKEN"` with `token=`). Test before building on it.
- Embedding model names change often. Before relying on embeddings, run one tiny test query. If no
  embedding model works within 10 minutes, `similar_scams` returns `[]` and we move on.

## Secrets — strict rules
- Credentials live ONLY in `.streamlit/secrets.toml` (section `[snowflake]`). Each person has their own copy.
- `.streamlit/secrets.toml`, `.venv/`, and `data/*.csv` must be in `.gitignore`. Run `git status` before every commit.
- Never print, log, or hardcode a token. Never ask the human to paste a token into chat.

## Snowflake objects (A creates them in `scripts/setup_snowflake.sql`)
Database `HIRESAFE`, schema `APP`:
- `JOB_POSTINGS`: the EMSCAD dataset (`data/fake_job_postings.csv`, ~18k rows, `fraudulent` 0/1). Only A has the CSV.
- `KNOWN_SCAMS`: id, source, text, embedding (VECTOR).
- `CHECKS`: id, created_at, input_text, verdict, risk_score, flags (VARIANT), model, latency_ms.
- `EVAL_RESULTS`: run_id, created_at, n, precision, recall, f1, unverified_quote_rate, notes.

## Analysis pipeline (`pipeline.check`)
1. `run_rules`: deterministic checks for payment, fees, equipment, or training costs; crypto, gift cards,
   check deposits; moving to WhatsApp, Telegram, or Signal; personal email domains (gmail, yahoo, outlook)
   claiming to represent a company; unrealistically high pay for little work; urgency; "no interview" or
   instant hire; early requests for SSN or bank details; task scams (liking videos, rating products);
   reshipping packages. Each rule returns the exact matched span.
2. `analyze`: Llama returns strict JSON. Validate it; on invalid JSON, retry up to 2 times with the parse error.
3. `verify_quotes`: every flag's quote must appear verbatim in the input (case-insensitive,
   whitespace-normalized). Drop unverified flags and count them.
4. `similar_scams`: top 3 matches (may be empty).
5. Combine rule flags and the LLM score into the final verdict and score with simple, documented thresholds.
6. `log_check` (never blocks the user if logging fails).

## UI (`app.py`, Streamlit)
Example dropdown (3 messages), text area, Check button. Verdict badge (red, yellow, or green) and risk score;
the input with flagged phrases highlighted; the red-flag list with explanations; similar scams; next steps;
disclaimer. Sidebar: today's tally from `get_tally()` (counts only, never other people's messages).
Clean layout: it will be demoed on a projector.

## Evaluation (`scripts/evaluate.py`, A)
Balanced sample from `JOB_POSTINGS` (50 fraudulent + 50 real; thread pool of 4–8 workers) run through
`pipeline.check`. Report precision, recall, F1, and the unverified-quote rate. Save to `EVAL_RESULTS`,
print a markdown table for the README. Only report numbers that were actually measured.

## Stretch: investigator agent (A builds `agent.py`; B adds a UI panel) — only if the core works by ~1:45
Llama acts as an investigator in a loop of at most 4 steps. Each step it outputs one JSON action, our code
validates and runs it, and the result goes back to the model. Tools: `search_known_scams(text)`,
`check_email_domain(email, claimed_company)`, `get_scam_pattern(category)`, `run_rules(text)`,
`final_verdict(...)`. Return the step-by-step trajectory so the UI can show an "investigation timeline."
This is a custom tool-calling loop because Cortex has no native tool calling for open-weight models.

## Timeline and sync points
- **11:20–11:45** A: secrets, config, connection, `llm.chat`, setup SQL; push skeleton ASAP.
  B: clone, environment, `rules.py`, `sample_messages.json`, `app.py` skeleton using a stub pipeline.
- **11:45 Sync 1**: B pulls; both confirm `llm.chat` works from their own laptop.
- **11:45–1:00** A: `load_data.py`, `store.py`, embedding test. B: `analysis.py`, `verify.py`, `pipeline.py`, `check.py`.
- **1:00 Sync 2**: `python scripts/check.py` works end to end on both laptops.
- **1:00–1:45** A: `similarity.py`, `build_embeddings.py`. B: wire `app.py` to the real pipeline, logging, tally, highlights.
- **1:45 Sync 3**: decide on the stretch agent (only if everything above works).
- **1:45–2:45** A: `evaluate.py` and results (then agent if chosen). B: UI polish, demo messages, `SKILL.md`, README draft.
- **2:45–3:15** Both: final pull, smoke test, A adds eval numbers to README, push. **Submit by 3:25.**
If behind, cut in this order: stretch agent → similarity → sidebar tally. Never cut the core check.

## Git workflow
- Both work on `main`, only in their own files. Commit small and often with clear messages.
- Before every push: `git pull --rebase origin main`, then a quick smoke test
  (`python -c "import hiresafe.pipeline"`, or run `scripts/check.py` once it exists), then push.
- On a rebase conflict, stop and tell the human. Never resolve a conflict by deleting the other person's work.
- Never commit `.streamlit/secrets.toml`, `.venv/`, or `data/*.csv`.

## Working style
- Plan briefly before each task; list the files you'll touch.
- Run and test after each change; show command output when something fails.
- Ask before deleting files, dropping tables, or rewriting working code.
- Keep functions small and readable; both of us need to explain this code to judges.
