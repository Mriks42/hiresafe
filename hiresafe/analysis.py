"""LLM analysis: ask Llama (via Cortex) for a strict-JSON scam assessment and validate it."""
import json
import logging
import re

from hiresafe.llm import chat_with_model

log = logging.getLogger(__name__)

MAX_RETRIES = 2
VERDICTS = {"likely_scam", "suspicious", "looks_legit"}
CATEGORIES = [
    "payment_request", "crypto_or_gift_card", "messaging_app_redirect", "personal_email_domain",
    "unrealistic_pay", "urgency", "instant_hire", "early_personal_info", "task_scam", "reshipping",
    "fake_check", "impersonation", "vague_details", "other",
]

SYSTEM_PROMPT = f"""You are HireSafe, an expert at spotting job and recruitment scams.
Analyze the message the user provides and respond with ONLY a JSON object, no prose, no markdown fences.

Schema:
{{
  "verdict": "likely_scam" | "suspicious" | "looks_legit",
  "risk_score": integer 0-100 (0 = clearly legitimate, 100 = certainly a scam),
  "red_flags": [
    {{"quote": "<exact phrase copied verbatim from the message>",
      "category": one of {json.dumps(CATEGORIES)},
      "explanation": "<one plain-English sentence on why this is a warning sign>"}}
  ],
  "summary": "<1-2 sentences explaining the verdict>",
  "advice": ["<short, specific next step>", ...]
}}

Rules:
- Every "quote" MUST be copied character-for-character from the message. Keep quotes short (2-12 words).
  Never paraphrase. If you cannot quote it exactly, leave that flag out.
- Read the ENTIRE message. Scammers hide a single request for money inside an otherwise genuine-looking
  posting. If the candidate is asked anywhere to pay, deposit, send a check, or post a bond, the verdict
  is likely_scam, however legitimate the rest looks.
- Categories: payment_request = the candidate pays or buys anything (fees, equipment from a "vendor");
  fake_check = a check sent to the candidate; reshipping = receiving and forwarding packages only.
- A legitimate message can have zero red flags; do not invent flags.
- Base the verdict only on concrete red flags in the text. Gibberish, very short text, or text that
  isn't about a job is NOT evidence of a scam: with no red flags, use a low risk_score and say in the
  summary that there isn't enough information to judge.
- Give 2-4 advice items."""


def _extract_json(raw: str) -> dict:
    """Parse the model output, tolerating ```json fences or stray text around the object."""
    raw = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in response")
    return json.loads(raw[start:end + 1])


def _validate(data: dict) -> dict:
    """Check the schema and normalize it into the analyze() contract. Raises ValueError if invalid."""
    if not isinstance(data, dict):
        raise ValueError("top-level JSON must be an object")
    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VERDICTS)}, got {verdict!r}")
    score = data.get("risk_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
        raise ValueError(f"risk_score must be a number 0-100, got {score!r}")
    raw_flags = data.get("red_flags", [])
    if not isinstance(raw_flags, list):
        raise ValueError("red_flags must be a list")

    flags = []
    for f in raw_flags:
        if not isinstance(f, dict) or not isinstance(f.get("quote"), str) or not f["quote"].strip():
            raise ValueError(f"each red flag needs a non-empty string 'quote', got {f!r}")
        category = f.get("category") if f.get("category") in CATEGORIES else "other"
        flags.append({
            "quote": f["quote"].strip(),
            "category": category,
            "explanation": str(f.get("explanation", "")).strip(),
            "source": "llm",
        })

    advice = data.get("advice", [])
    if not isinstance(advice, list):
        advice = [str(advice)]
    return {
        "verdict": verdict,
        "risk_score": int(round(score)),
        "red_flags": flags,
        "summary": str(data.get("summary", "")).strip(),
        "advice": [str(a).strip() for a in advice if str(a).strip()],
    }


def analyze(text: str) -> dict:
    """Return the LLM's assessment of `text`. Retries up to MAX_RETRIES times on invalid JSON.

    Also includes "model": the model that actually answered (llama3.1-8b if the 70b call fell back).
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Message to analyze:\n\"\"\"\n{text}\n\"\"\""},
    ]
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        raw, model = chat_with_model(messages)
        try:
            return {**_validate(_extract_json(raw)), "model": model}
        except ValueError as e:  # json.JSONDecodeError is a ValueError
            last_error = e
            log.warning("analyze attempt %d returned invalid JSON: %s", attempt + 1, e)
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That response was invalid: {e}. "
                                            "Reply again with ONLY the JSON object matching the schema."},
            ]
    raise ValueError(f"LLM returned invalid JSON after {MAX_RETRIES + 1} attempts: {last_error}")
