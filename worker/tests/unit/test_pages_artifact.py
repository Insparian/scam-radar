from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.check_pages_artifact import validate_pages_artifact


def write_minimal_artifact(root: Path, release_id: str = "fixture-release") -> None:
    root.mkdir()
    (root / "index.html").write_text("home", encoding="utf-8")
    (root / "404.html").write_text("missing", encoding="utf-8")
    (root / "release.json").write_text(json.dumps({"release_id": release_id}), encoding="utf-8")
    (root / "search-index.json").write_text("{}", encoding="utf-8")


def test_pages_artifact_records_a_stable_summary(tmp_path: Path) -> None:
    root = tmp_path / "out"
    write_minimal_artifact(root)

    first = validate_pages_artifact(root, "fixture-release")
    second = validate_pages_artifact(root, "fixture-release")

    assert first == second
    assert first.file_count == 4
    assert len(first.artifact_hash) == 64


def test_pages_artifact_rejects_release_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "out"
    write_minimal_artifact(root)

    with pytest.raises(RuntimeError, match="release mismatch"):
        validate_pages_artifact(root, "another-release")


@pytest.mark.parametrize("runtime_file", ["_worker.js", "_routes.json"])
def test_pages_artifact_rejects_runtime_entrypoints(tmp_path: Path, runtime_file: str) -> None:
    root = tmp_path / "out"
    write_minimal_artifact(root)
    (root / runtime_file).write_text("runtime", encoding="utf-8")

    with pytest.raises(RuntimeError, match="runtime entrypoint"):
        validate_pages_artifact(root, "fixture-release")
