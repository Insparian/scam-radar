from __future__ import annotations

from scam_radar.cli import repository_root
from scam_radar.settings import Settings


def test_default_repository_root_contains_project_contract() -> None:
    root = repository_root()
    assert (root / "AGENTS.md").is_file()
    assert Settings.from_environment().repository_root == root
