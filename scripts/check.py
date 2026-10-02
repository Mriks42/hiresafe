"""CLI: read a message from stdin, print the HireSafe result as JSON.

Usage:  echo "Pay a $50 fee to start" | python scripts/check.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hiresafe.pipeline import check  # noqa: E402


def main() -> None:
    text = sys.stdin.read().strip()
    if not text:
        sys.exit("No input: pipe a message into stdin.")
    print(json.dumps(check(text), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
