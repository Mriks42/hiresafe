---
name: hiresafe-check
description: Check a job posting, recruiter email, LinkedIn message, or text message for signs of a job scam using HireSafe (open-weight Llama 3.1 70B on Snowflake Cortex plus rule-based checks). Use when the user asks whether a job offer, recruiter, or hiring message is legitimate, fake, or a scam.
license: Apache-2.0
compatibility: Requires Python 3.11+, the HireSafe repository with its .venv installed, and Snowflake Cortex credentials in .streamlit/secrets.toml.
---

# HireSafe check

Use HireSafe to assess whether a job-related message is a scam, then explain the result to the user.

## Steps

1. Get the full text of the message from the user. If they only describe it, ask them to paste it.
   Remove the user's own personal details (their phone number, address, SSN) before checking. The
   text is sent to Snowflake and may be logged.
2. From the HireSafe repository root, pipe the text into the checker. Use a heredoc so quotes and `$`
   signs in the message are passed through unchanged:

   ```bash
   .venv/bin/python scripts/check.py <<'EOF'
   <the message text>
   EOF
   ```

3. The script prints one JSON object:

   | Field | Meaning |
   |---|---|
   | `verdict` | `likely_scam`, `suspicious`, or `looks_legit` |
   | `risk_score` | 0–100 |
   | `flags` | list of `{quote, category, explanation, source}`; every `quote` appears word-for-word in the message |
   | `similar` | up to 3 known scams: `{text, source, score}` |
   | `summary` | one or two sentences from the model |
   | `advice` | next steps |
   | `dropped_quotes` | model quotes removed because they weren't in the message |
   | `model` | the model that answered; `rules-only` means the LLM was unavailable |
   | `latency_ms` | time taken |

4. Report back to the user:
   - Lead with the verdict and risk score in plain words (for example, "This looks like a scam, 85/100").
   - List the red flags, quoting each `quote` exactly and giving its explanation. Don't add red flags
     that aren't in the output.
   - If `similar` is not empty, mention that it resembles known scams.
   - Give the `advice` items as next steps.
   - End with: this is guidance, not a guarantee; verify the job on the company's official careers
     page and report scams at https://reportfraud.ftc.gov.

## If something goes wrong

- `model` is `rules-only`: the LLM call failed, so the result comes from the fixed rule checks only.
  Say so, and treat a `looks_legit` verdict with extra caution.
- An error mentioning `secrets.toml`: credentials aren't set up. Point the user to the README's
  "Run it yourself" section. Never ask the user to paste a token into the chat.
- An authentication error from Snowflake: the token's network-policy bypass may have expired; it can be
  re-granted in Snowsight.
