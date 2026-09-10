from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "node_modules",
    "playwright-report",
    "test-results",
    "work",
}
SECRET_PATTERNS = {
    "AWS access key ID": re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "GitHub token": re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}"),
    "OpenAI-style secret": re.compile(r"\bsk-[0-9A-Za-z_-]{24,}"),
    "Supabase secret key": re.compile(r"\bsb_secret_[0-9A-Za-z_-]{20,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
EXPORT_SENTINELS = (
    "SUPABASE_SECRET_KEY",
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_ACCESS_TOKEN",
    "GEMINI_API_KEY",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_R2_ACCESS_KEY_ID",
    "CLOUDFLARE_R2_SECRET_ACCESS_KEY",
)


def text_files(root: Path) -> Iterator[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        yield path


def content_findings(content: str, *, export: bool) -> list[str]:
    findings = [
        label for label, pattern in SECRET_PATTERNS.items() if pattern.search(content)
    ]
    if export:
        findings.extend(
            f"private variable name {sentinel}"
            for sentinel in EXPORT_SENTINELS
            if sentinel in content
        )
    return findings


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def scan(root: Path, *, export: bool) -> list[str]:
    findings: list[str] = []
    for path in text_files(root):
        content = path.read_text(encoding="utf-8")
        findings.extend(
            f"{display_path(path)}: possible {label}"
            for label in content_findings(content, export=export)
        )
    return findings


def git_output(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=60,
    )
    return result.stdout


def scan_history() -> list[str]:
    """Scan every unique text blob reachable from the local Git history.

    Findings include only a path, object ID, and secret type. Secret values are never
    echoed into a terminal or CI log.
    """

    revisions = git_output("rev-list", "--all").decode("ascii").splitlines()
    if not revisions:
        raise RuntimeError("Git history is empty")

    blobs: dict[str, tuple[str, str]] = {}
    for revision in revisions:
        tree = git_output("ls-tree", "-r", "-z", "--full-tree", revision)
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            _, object_type, object_id = metadata.split(b" ", 2)
            if object_type != b"blob":
                continue
            blobs.setdefault(
                object_id.decode("ascii"),
                (revision[:12], raw_path.decode("utf-8", errors="replace")),
            )

    findings: list[str] = []
    for object_id, (revision, path) in blobs.items():
        raw = git_output("cat-file", "blob", object_id)
        if b"\0" in raw[:8192]:
            continue
        content = raw.decode("utf-8", errors="ignore")
        findings.extend(
            f"history:{path}@{revision} ({object_id[:12]}): possible {label}"
            for label in content_findings(content, export=False)
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--repo", action="store_true")
    mode.add_argument("--history", action="store_true")
    mode.add_argument("--export", type=Path)
    args = parser.parse_args()
    if args.history:
        findings = scan_history()
        mode_name = "full Git history"
    else:
        target = ROOT if args.repo else args.export.resolve()
        if not target.exists():
            raise RuntimeError(f"scan target does not exist: {target}")
        findings = scan(target, export=args.export is not None)
        mode_name = "static export" if args.export is not None else "repository"
    if findings:
        raise RuntimeError("secret scan failed:\n" + "\n".join(findings))
    print(f"secret scan ok: {mode_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
