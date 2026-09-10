from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command_version(command: str, argument: str = "--version") -> str:
    path = shutil.which(command)
    if path is None:
        raise RuntimeError(f"required command is missing: {command}")
    result = subprocess.run(
        [path, argument],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return (result.stdout or result.stderr).strip().splitlines()[0]


def require_files() -> None:
    required = (
        "AGENTS.md",
        "worker/uv.lock",
        "web/package-lock.json",
        "config/sources.yaml",
        "config/models.yaml",
        "evals/expected/behavior-manifest.json",
        "supabase/config.toml",
    )
    missing = [relative for relative in required if not (ROOT / relative).is_file()]
    if missing:
        raise RuntimeError(
            f"required repository files are missing: {', '.join(missing)}"
        )


def require_offline_defaults() -> None:
    models = (ROOT / "config/models.yaml").read_text(encoding="utf-8")
    required_lines = (
        "live_enabled: false",
        "production_model: null",
        "embedding_enabled: false",
    )
    if any(line not in models for line in required_lines):
        raise RuntimeError("config/models.yaml no longer fails closed")

    registry = json.loads((ROOT / "config/sources.yaml").read_text(encoding="utf-8"))
    unsafe = [source["key"] for source in registry["sources"] if source["enabled"]]
    unsafe.extend(
        source["key"]
        for source in registry["sources"]
        if source["policy"]["collection_allowed"]
    )
    if unsafe:
        raise RuntimeError(
            f"external sources are enabled before activation: {sorted(set(unsafe))}"
        )

    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    required_disabled_switches = (
        "SCAM_RADAR_COLLECT_ENABLED=false",
        "SCAM_RADAR_AI_ENABLED=false",
        "SCAM_RADAR_DEPLOY_ENABLED=false",
        "SCAM_RADAR_BACKUP_ENABLED=false",
    )
    if any(line not in env_example for line in required_disabled_switches):
        raise RuntimeError(".env.example no longer fails closed")


def main() -> int:
    require_files()
    require_offline_defaults()
    node = command_version("node")
    npm = command_version("npm")
    python = sys.version.split()[0]
    try:
        node_major = int(node.removeprefix("v").split(".", 1)[0])
    except ValueError as error:
        raise RuntimeError(f"could not parse Node version: {node}") from error
    if node_major < 24:
        raise RuntimeError("Node 24 or newer is required")
    if sys.version_info < (3, 13):
        raise RuntimeError(
            "Python 3.13 or newer is required; the pinned CI version is 3.13"
        )
    print(f"environment ok: node={node} npm={npm} python={python} mode=offline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
