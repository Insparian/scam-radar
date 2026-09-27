from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError

from scripts.rehearse_deploy import RehearsalServer


def write_artifact(root: Path, release_id: str) -> None:
    root.mkdir()
    (root / "index.html").write_text(release_id, encoding="utf-8")
    (root / "404.html").write_text("missing", encoding="utf-8")
    (root / "release.json").write_text(json.dumps({"release_id": release_id}), encoding="utf-8")
    (root / "search-index.json").write_text(
        json.dumps({"release_id": release_id, "items": []}), encoding="utf-8"
    )
    (root / "search").mkdir()
    (root / "search" / "index.html").write_text(release_id, encoding="utf-8")


def test_executable_rehearsal_preserves_and_restores_original_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    write_artifact(artifact, "release-2026-09-20")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/rehearse_deploy.py",
            "--artifact",
            str(artifact),
            "--release-id",
            "release-2026-09-20",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "offline deploy rehearsal passed" in result.stdout


def test_rehearsal_server_rejects_older_release_on_the_rpc_boundary(tmp_path: Path) -> None:
    from scripts.deploy_public_release import JsonHttp, ReleaseRpc, artifact_hash

    artifact = tmp_path / "artifact"
    write_artifact(artifact, "release-2026-09-20")
    with RehearsalServer("release-2026-09-20", artifact_hash(artifact)) as server:
        rpc = ReleaseRpc(JsonHttp(server.origin))
        try:
            rpc.mark_deploying("older-release", artifact_hash(artifact), "a" * 40)
        except HTTPError:
            pass
        else:
            raise AssertionError("older release unexpectedly accepted")


def test_publication_command_requires_switch_and_exact_confirmation(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    write_artifact(artifact, "release-2026-09-20")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/deploy_public_release.py",
            "--artifact",
            str(artifact),
            "--release-id",
            "release-2026-09-20",
            "--commit-sha",
            "a" * 40,
            "--rpc-origin",
            "http://127.0.0.1:1",
            "--pages-origin",
            "http://127.0.0.1:1",
            "--confirmation",
            "wrong confirmation",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "deployment_rehearsal_not_authorized" in result.stderr
