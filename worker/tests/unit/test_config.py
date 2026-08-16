from __future__ import annotations

import json

import pytest

from scam_radar.config import load_registry


def test_registry_is_valid_and_all_candidates_are_disabled(repository_root):  # type: ignore[no-untyped-def]
    registry = load_registry(
        repository_root / "config/sources.yaml",
        repository_root / "config/sources.schema.json",
        repository_root,
    )
    assert len(registry.sources) == 15
    assert not any(source["enabled"] for source in registry.sources)
    assert len(registry.content_hash) == 64


def test_enabled_source_requires_reviewed_permission(repository_root, tmp_path):  # type: ignore[no-untyped-def]
    data = json.loads((repository_root / "config/sources.yaml").read_text())
    data["sources"][0]["enabled"] = True
    path = tmp_path / "sources.yaml"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed collection permission"):
        load_registry(path, repository_root / "config/sources.schema.json", repository_root)


def test_registry_rejects_duplicate_keys(repository_root, tmp_path):  # type: ignore[no-untyped-def]
    data = json.loads((repository_root / "config/sources.yaml").read_text())
    data["sources"][1]["key"] = data["sources"][0]["key"]
    path = tmp_path / "sources.yaml"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate source keys"):
        load_registry(path, repository_root / "config/sources.schema.json", repository_root)
