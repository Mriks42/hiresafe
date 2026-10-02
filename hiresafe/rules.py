import re

# Pay at or above these amounts is flagged as unrealistic. Lower thresholds fired on ordinary
# wages like "$15 per hour" in genuine postings.
MIN_UNREALISTIC_PAY = {"hour": 100, "hr": 100, "day": 800, "week": 2000, "wk": 2000}


def _pay_is_unrealistic(match: re.Match) -> bool:
    amount = float(match.group("amt").replace(",", ""))
    return amount >= MIN_UNREALISTIC_PAY[match.group("unit").lower()]


# Each rule: regex patterns (case-insensitive). If a pattern has a named group "q", only that group is
# quoted. An optional "keep" function can reject a match (used for pay thresholds).
_RULES = [
    {
        "category": "payment_request",
        "patterns": [
            r"\b(?:registration|processing|application|training|admin|administrative)\s+fee\b",
            r"\b(?:pay|payment)\s+(?:for|of)\s+(?:your\s+own\s+)?(?:equipment|starter kit|training materials?)\b",
            r"\bupfront\s+(?:cost|payment|fee)\b",
            r"\bbuy\s+(?:your\s+own\s+)?(?:equipment|laptop|starter kit)\b",
        ],
        "explanation": "Legitimate employers never ask candidates to pay fees or buy equipment before being hired.",
    },
    {
        "category": "crypto_or_gift_card",
        "patterns": [
            # Crypto only in a payment context, so genuine crypto-company postings don't trigger it.
            r"\b(?:pay|paid|payment|send|sent|deposit|transfer|fee|via|using)\b[^.\n]{0,40}?"
            r"\b(?P<q>bitcoin|btc|ethereum|usdt|crypto(?:currency)?)\b",
            r"\b(?:gift\s*cards?|itunes\s*card|google\s*play\s*card|amazon\s*gift\s*card)\b",
            r"\bcash(?:ier'?s)?\s+check\b",
            r"\bdeposit\s+(?:the\s+)?check\b",
        ],
        "explanation": "Requests involving cryptocurrency, gift cards, or depositing checks are classic scam payment methods.",
    },
    {
        "category": "messaging_app_redirect",
        "patterns": [
            r"\b(?:text|message|contact|reach)\s+(?:me|us)?\s*(?:on|via)\s+(?:whatsapp|telegram|signal)\b",
        ],
        "explanation": "Scammers often move conversations off official channels to WhatsApp, Telegram, or Signal to avoid detection.",
    },
    {
        "category": "personal_email_domain",
        "patterns": [
            r"[\w.+-]+@(?:gmail|yahoo|outlook|hotmail)\.com",
        ],
        "explanation": "A recruiter using a personal email domain instead of a company domain is a common impersonation tactic.",
    },
    {
        "category": "unrealistic_pay",
        "patterns": [
            r"\$\s?(?P<amt>\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?\s*(?:per|/|an?)\s*(?P<unit>hour|hr|day|week|wk)\b",
        ],
        "keep": _pay_is_unrealistic,
        "explanation": "Unusually high pay for minimal work is a common lure in job scams.",
    },
    {
        "category": "urgency",
        "patterns": [
            # Not bare "urgent"/"immediately"/"right away": genuine postings say "start immediately" a lot.
            r"\b(?:act\s+now|limited\s+time|hurry|don'?t\s+miss\s+out|today\s+only|asap)\b",
            r"\b(?:only\s+)?(?:a\s+)?few\s+(?:slots|spots|positions)\s+(?:left|remaining)\b",
            r"\blimited\s+(?:slots|spots)\b",
        ],
        "explanation": "Pressuring a candidate to act fast is used to short-circuit normal verification.",
    },
    {
        "category": "instant_hire",
        "patterns": [
            r"\bno\s+interview(?:s)?(?:\s+(?:needed|required|necessary))?\b",
            r"\binstant(?:ly)?\s+hired?\b",
            r"\bhired?\s+on\s+the\s+spot\b",
            r"\bguaranteed\s+(?:job|position|hire)\b",
        ],
        "explanation": "Real hiring involves interviews and vetting; skipping that entirely is a red flag.",
    },
    {
        "category": "early_personal_info",
        "patterns": [
            r"\bsocial\s+security\s+number\b",
            r"\bssn\b",
            r"\bbank\s+account\s+(?:number|details)\b",
            r"\brouting\s+number\b",
            r"\bdate\s+of\s+birth\b",
        ],
        "explanation": "Legitimate employers don't ask for SSNs or bank details before an offer and background check.",
    },
    {
        "category": "task_scam",
        "patterns": [
            r"\blike\s+(?:and\s+share\s+)?videos?\b",
            r"\brate\s+products?\b",
            r"\bwatch\s+videos?\s+(?:for|to\s+earn)\b",
            r"\bcomplete\s+simple\s+tasks?\b",
        ],
        "explanation": "Paying people to like videos or rate products is a known task-scam pattern, not real work.",
    },
    {
        "category": "reshipping",
        "patterns": [
            r"\breship(?:ping)?\b",
            r"\bforward(?:ing)?\s+(?:a\s+)?packages?\b",
            r"\breceive\s+(?:and\s+)?(?:re)?ship\s+packages?\b",
        ],
        "explanation": "Reshipping packages for an unknown employer is frequently used to launder stolen goods.",
    },
]


def run_rules(text: str) -> list[dict]:
    flags = []
    seen = set()
    for rule in _RULES:
        for pattern in rule["patterns"]:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if "keep" in rule and not rule["keep"](match):
                    continue
                quote = match.group("q") if "q" in match.re.groupindex else match.group(0)
                key = (rule["category"], quote.lower())
                if key in seen:
                    continue
                seen.add(key)
                flags.append({
                    "quote": quote,
                    "category": rule["category"],
                    "explanation": rule["explanation"],
                    "source": "rule",
                })
    return flags



CATEGORIES = [rule["category"] for rule in _RULES]


def describe_category(category: str) -> str | None:
    """Plain-English description of a rule category, or None if unknown."""
    return next((r["explanation"] for r in _RULES if r["category"] == category), None)


if __name__ == "__main__":
    _SMOKE_TESTS = [
        (
            "Send a $50 registration fee via Bitcoin and message me on WhatsApp ASAP, "
            "you're hired on the spot!",
            {"payment_request", "crypto_or_gift_card", "messaging_app_redirect", "urgency", "instant_hire"},
        ),
        (
            "We'd like to schedule a 30-minute interview next Tuesday to discuss the Software Engineer role.",
            set(),
        ),
    ]
    for text, expected_categories in _SMOKE_TESTS:
        found = run_rules(text)
        found_categories = {f["category"] for f in found}
        ok = expected_categories <= found_categories and (expected_categories or not found_categories)
        print(f"[{'OK' if ok else 'FAIL'}] {len(found)} flag(s) -> {sorted(found_categories)}")
        for f in found:
            print(f"    {f['category']!r}: {f['quote']!r}")
