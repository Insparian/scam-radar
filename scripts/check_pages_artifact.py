from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

MAX_FILES = 20_000
MAX_FILE_BYTES = 25 * 1024 * 1024
REQUIRED_FILES = {
    Path("index.html"),
    Path("404.html"),
    Path("release.json"),
    Path("search-index.json"),
}
FORBIDDEN_RUNTIME_FILES = {Path("_worker.js"), Path("_routes.json")}


@dataclass(frozen=True)
class ArtifactSummary:
    release_id: str
    file_count: int
    total_bytes: int
    artifact_hash: str


def validate_pages_artifact(root: Path, expected_release_id: str) -> ArtifactSummary:
    if not root.is_dir():
        raise RuntimeError(f"Pages artifact directory does not exist: {root}")

    paths = sorted(path for path in root.rglob("*") if path.is_file())
    relative_paths = {path.relative_to(root) for path in paths}
    missing = sorted(REQUIRED_FILES - relative_paths)
    if missing:
        raise RuntimeError(
            "Pages artifact is missing required files: "
            + ", ".join(path.as_posix() for path in missing)
        )
    forbidden = sorted(FORBIDDEN_RUNTIME_FILES & relative_paths)
    if forbidden:
        raise RuntimeError(
            "Pages artifact unexpectedly contains a runtime entrypoint: "
            + ", ".join(path.as_posix() for path in forbidden)
        )
    if len(paths) > MAX_FILES:
        raise RuntimeError(
            f"Pages artifact has {len(paths)} files; Free plan limit is {MAX_FILES}"
        )

    total_bytes = 0
    digest = hashlib.sha256()
    for path in paths:
        if path.is_symlink():
            raise RuntimeError(
                f"Pages artifact contains a symlink: {path.relative_to(root)}"
            )
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise RuntimeError(
                f"Pages artifact file exceeds 25 MiB: {path.relative_to(root)}"
            )
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        total_bytes += size

    release = json.loads((root / "release.json").read_text(encoding="utf-8"))
    release_id = release.get("release_id")
    if release_id != expected_release_id:
        raise RuntimeError(
            f"Pages artifact release mismatch: expected {expected_release_id}, got {release_id}"
        )

    return ArtifactSummary(
        release_id=expected_release_id,
        file_count=len(paths),
        total_bytes=total_bytes,
        artifact_hash=digest.hexdigest(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a static artifact before Cloudflare Pages upload."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    summary = validate_pages_artifact(args.root.resolve(), args.release_id)
    print(
        "pages artifact ok: "
        f"release_id={summary.release_id} files={summary.file_count} "
        f"bytes={summary.total_bytes} sha256={summary.artifact_hash}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
