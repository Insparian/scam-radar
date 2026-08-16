from __future__ import annotations

import argparse
import re
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


def scan(root: Path, *, export: bool) -> list[str]:
    findings: list[str] = []
    for path in text_files(root):
        content = path.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: possible {label}")
        if export:
            for sentinel in EXPORT_SENTINELS:
                if sentinel in content:
                    findings.append(
                        f"{path.relative_to(ROOT)}: private variable name {sentinel}"
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", action="store_true")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    if args.repo == (args.export is not None):
        parser.error("choose exactly one of --repo or --export PATH")
    target = ROOT if args.repo else args.export.resolve()
    if not target.exists():
        raise RuntimeError(f"scan target does not exist: {target}")
    findings = scan(target, export=args.export is not None)
    if findings:
        raise RuntimeError("secret scan failed:\n" + "\n".join(findings))
    mode = "static export" if args.export is not None else "repository"
    print(f"secret scan ok: {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
