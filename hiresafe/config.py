"""Settings loaded from .streamlit/secrets.toml, section [snowflake]."""
import tomllib
from functools import lru_cache
from pathlib import Path

SECRETS_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
REQUIRED_KEYS = ["account", "host", "user", "role", "warehouse", "pat"]
DEFAULT_MODEL = "llama3.1-70b"
FALLBACK_MODEL = "llama3.1-8b"
EMBED_MODEL = "e5-base-v2"  # 768-dim; tested with SNOWFLAKE.CORTEX.EMBED_TEXT_768


@lru_cache(maxsize=1)
def get_settings() -> dict:
    """Return the [snowflake] settings plus model defaults. Never print the result: it holds the PAT."""
    if not SECRETS_PATH.exists():
        raise FileNotFoundError(f"Missing {SECRETS_PATH}; copy the template and fill in your values.")
    with open(SECRETS_PATH, "rb") as f:
        settings = dict(tomllib.load(f).get("snowflake", {}))
    missing = [k for k in REQUIRED_KEYS if not settings.get(k)]
    if missing:
        raise KeyError(f"secrets.toml [snowflake] is missing: {', '.join(missing)}")
    settings.setdefault("model", DEFAULT_MODEL)
    settings.setdefault("fallback_model", FALLBACK_MODEL)
    settings.setdefault("embed_model", EMBED_MODEL)
    return settings
