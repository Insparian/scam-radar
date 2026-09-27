from __future__ import annotations

import pytest

from scam_radar.cli import repository_root, run_batch
from scam_radar.settings import Settings


def test_default_repository_root_contains_project_contract() -> None:
    root = repository_root()
    assert (root / "AGENTS.md").is_file()
    assert Settings.from_environment().repository_root == root


def test_batch_remains_closed_without_external_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    root = repository_root()
    monkeypatch.setenv("SCAM_RADAR_ENV", "local")
    monkeypatch.setenv("SCAM_RADAR_COLLECT_ENABLED", "false")
    monkeypatch.setenv("SCAM_RADAR_AI_ENABLED", "false")
    with pytest.raises(RuntimeError, match="batch_external_activation_required"):
        run_batch(root, "all")


def test_batch_refuses_unreviewed_registry_even_with_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    root = repository_root()
    monkeypatch.setenv("SCAM_RADAR_ENV", "production")
    monkeypatch.setenv("SCAM_RADAR_COLLECT_ENABLED", "true")
    monkeypatch.setenv("SCAM_RADAR_AI_ENABLED", "true")
    monkeypatch.setenv("SCAM_RADAR_DEPLOY_ENABLED", "false")
    monkeypatch.setenv("SCAM_RADAR_MAX_ITEMS_PER_RUN", "20")
    monkeypatch.setenv("SCAM_RADAR_MAX_ITEMS_PER_SOURCE", "10")
    with pytest.raises(RuntimeError, match="no_enabled_reviewed_source_selected"):
        run_batch(root, "all")
