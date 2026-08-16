from __future__ import annotations

import argparse
from pathlib import Path

from scam_radar.config import load_registry
from scam_radar.observability.summary import render_summary
from scam_radar.pipeline import FixturePipeline
from scam_radar.settings import Settings


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def validate_registry(root: Path) -> int:
    registry = load_registry(
        root / "config" / "sources.yaml",
        root / "config" / "sources.schema.json",
        root,
    )
    summary = (
        f"registry valid: {len(registry.sources)} disabled candidates, "
        f"hash={registry.content_hash[:12]}"
    )
    print(summary)
    return 0


def collect_dry_run(root: Path) -> int:
    settings = Settings.from_environment(root)
    if settings.collect_enabled or settings.ai_enabled or settings.deploy_enabled:
        raise RuntimeError("dry-run requires every external capability to remain disabled")
    return validate_registry(root)


def run_demo(root: Path, output_root: Path) -> int:
    summary = FixturePipeline(root).run(output_root)
    print(render_summary(summary))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scam-radar")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate-registry")
    subcommands.add_parser("collect-dry-run")
    demo = subcommands.add_parser("demo")
    demo.add_argument("--output", type=Path, default=Path("work/release"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = repository_root()
    if args.command == "validate-registry":
        return validate_registry(root)
    if args.command == "collect-dry-run":
        return collect_dry_run(root)
    if args.command == "demo":
        output = args.output if args.output.is_absolute() else root / args.output
        return run_demo(root, output)
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
