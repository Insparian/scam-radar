"""Block Cloudflare writes until the dedicated account ID is reviewed in Git."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "cloudflare-account.json"


def require_dedicated_account(account_id: str, config_path: Path = CONFIG) -> None:
    config = json.loads(config_path.read_text())
    reviewed_id = config.get("dedicated_account_id")
    if not isinstance(reviewed_id, str) or not re.fullmatch(
        r"[0-9a-f]{32}", reviewed_id
    ):
        raise ValueError("dedicated_cloudflare_account_not_reviewed")
    if account_id != reviewed_id:
        raise ValueError("cloudflare_account_mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    args = parser.parse_args()
    require_dedicated_account(args.account_id)


if __name__ == "__main__":
    main()
