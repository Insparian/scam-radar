from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PUBLIC_FILES = (
    "LICENSE",
    "NOTICE",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/open-source-boundary.md",
)
PROHIBITED_PARTS = {
    ".next",
    "node_modules",
    "playwright-report",
    "test-results",
    "work",
}
PROHIBITED_SUFFIXES = {
    ".bak",
    ".dump",
    ".key",
    ".p12",
    ".pem",
    ".pfx",
    ".sqlite",
    ".sqlite3",
}


def candidate_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=30,
    )
    return [
        Path(item.decode("utf-8", errors="replace"))
        for item in result.stdout.split(b"\0")
        if item
    ]


def boundary_failures(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        lowered_parts = {part.lower() for part in path.parts}
        if lowered_parts & PROHIBITED_PARTS:
            failures.append(f"prohibited generated/private path: {path}")
        if path.name == ".env" or (
            path.name.startswith(".env.") and path.name != ".env.example"
        ):
            failures.append(f"environment file must remain ignored: {path}")
        if path.suffix.lower() in PROHIBITED_SUFFIXES:
            failures.append(f"prohibited credential/backup file type: {path}")
    return failures


def main() -> int:
    missing = [path for path in REQUIRED_PUBLIC_FILES if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(
            f"required public-governance files missing: {', '.join(missing)}"
        )

    paths = candidate_paths()
    failures = boundary_failures(paths)
    if failures:
        raise RuntimeError("public boundary check failed:\n" + "\n".join(failures))

    print(f"public boundary ok: {len(paths)} tracked/unignored candidate files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
