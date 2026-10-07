import json

import pytest
from scripts.cloudflare_account_guard import require_dedicated_account


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
