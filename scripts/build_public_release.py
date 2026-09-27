"""Build an explicitly selected pre-exported release without database credentials."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from check_pages_artifact import validate_pages_artifact
from check_secrets import scan

ROOT = Path(__file__).resolve().parents[1]


def build(release_path: Path, release_id: str, destination: Path) -> str:
    payload = json.loads(release_path.read_text())
    if payload.get("release_id") != release_id or release_id.startswith("fixture-"):
        raise ValueError("explicit_nonfixture_release_required")
    if destination.exists():
        raise ValueError("artifact_destination_already_exists")
    # Allowlist environment: the build cannot inherit exporter/model/admin secrets.
    env = {
        key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR") if key in os.environ
    }
    env.update(
        SCAM_RADAR_ENV="production",
        SCAM_RADAR_RELEASE_PATH=str(release_path.resolve()),
        NEXT_PUBLIC_RELEASE_ID=release_id,
        NEXT_TELEMETRY_DISABLED="1",
    )
    generated_inputs = [
        ROOT / "web/public/release.json",
        ROOT / "web/public/search-index.json",
    ]
    originals = {
        path: path.read_bytes() if path.exists() else None for path in generated_inputs
    }
    try:
        subprocess.run(["npm", "run", "build"], cwd=ROOT / "web", env=env, check=True)
        artifact = ROOT / "web/out"
        if not payload["patterns"]:
            sentinel = artifact / "scam/release-empty"
            if not sentinel.is_dir():
                raise RuntimeError("empty_release_sentinel_missing")
            shutil.rmtree(sentinel)
        findings = scan(artifact, export=True)
        if findings:
            raise RuntimeError("public_artifact_secret_check_failed")
        summary = validate_pages_artifact(artifact, release_id)
        shutil.copytree(artifact, destination)
        if (
            validate_pages_artifact(destination, release_id).artifact_hash
            != summary.artifact_hash
        ):
            raise RuntimeError("artifact_copy_mismatch")
        return summary.artifact_hash
    finally:
        for path, original in originals.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(
        "public build passed: sha256="
        + build(args.release, args.release_id, args.destination)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
