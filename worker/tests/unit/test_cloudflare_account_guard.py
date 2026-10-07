import json
import tomllib

import pytest
from scripts.cloudflare_account_guard import ROOT, require_dedicated_account

WORKER_CONFIGS = (
    ROOT / "cloudflare/scheduler/wrangler.toml",
    ROOT / "cloudflare/backup-scheduler/wrangler.toml",
)
UNREVIEWED_ACCOUNT_ID = "0" * 32


def test_account_guard_fails_closed_until_reviewed(tmp_path):
    config = tmp_path / "account.json"
    config.write_text(json.dumps({"dedicated_account_id": None}))
    with pytest.raises(ValueError, match="not_reviewed"):
        require_dedicated_account("a" * 32, config)


def test_account_guard_requires_exact_account(tmp_path):
    config = tmp_path / "account.json"
    config.write_text(json.dumps({"dedicated_account_id": "a" * 32}))
    with pytest.raises(ValueError, match="mismatch"):
        require_dedicated_account("b" * 32, config)
    require_dedicated_account("a" * 32, config)


def test_direct_wrangler_commands_target_only_reviewed_account():
    reviewed_id = json.loads((ROOT / "config/cloudflare-account.json").read_text())[
        "dedicated_account_id"
    ]
    expected_id = reviewed_id or UNREVIEWED_ACCOUNT_ID
    for config_path in WORKER_CONFIGS:
        worker = tomllib.loads(config_path.read_text())
        assert worker["account_id"] == expected_id, str(config_path)
        if reviewed_id:
            require_dedicated_account(worker["account_id"])
