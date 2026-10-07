from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from scam_radar.collectors.http import BoundedHttpTransport
from scam_radar.collectors.source import SourceCollector
from scam_radar.config import load_registry
from scam_radar.durable import DurablePipeline
from scam_radar.llm.http_provider import HttpModelProvider
from scam_radar.observability.summary import render_summary
from scam_radar.pipeline import FixturePipeline
from scam_radar.policy.engine import load_publication_policy
from scam_radar.settings import Settings
from scam_radar.storage.rpc import RpcStore


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


def _behavior_hash(root: Path) -> str:
    files = [
        root / "config/models.yaml",
        root / "config/scoring-v0.1.yaml",
        root / "config/publication-policy-v0.1.yaml",
        *sorted((root / "prompts").glob("*.md")),
        *sorted((root / "contracts/schemas").glob("*.json")),
    ]
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _external_origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("external_endpoint_requires_https")
    return f"https://{parts.netloc}"


def run_batch(root: Path, source_key: str) -> int:
    settings = Settings.from_environment(root)
    if (
        settings.environment != "production"
        or not settings.collect_enabled
        or not settings.ai_enabled
    ):
        raise RuntimeError("batch_external_activation_required")
    if settings.deploy_enabled:
        raise RuntimeError("batch_must_not_enable_deployment")
    if settings.registry_path.resolve() != (root / "config/sources.yaml").resolve():
        raise RuntimeError("production_requires_reviewed_registry")
    if settings.max_items_per_run > 20 or settings.max_items_per_source > 10:
        raise RuntimeError("batch_rpc_budget_requires_at_most_20_items_10_per_source")
    if settings.max_ai_calls_per_run == 0:
        raise RuntimeError("batch_model_call_budget_required")
    registry = load_registry(settings.registry_path, root / "config/sources.schema.json", root)
    selected = [
        source
        for source in registry.sources
        if source["enabled"] and source_key in {"all", source["key"]}
    ]
    if not selected or (source_key != "all" and len(selected) != 1):
        raise RuntimeError("no_enabled_reviewed_source_selected")
    model_config = yaml.safe_load((root / "config/models.yaml").read_text(encoding="utf-8"))
    model_key = model_config.get("production_model")
    if (
        not model_config.get("live_enabled")
        or model_key not in model_config["evaluation_candidates"]
    ):
        raise RuntimeError("reviewed_production_model_required")
    candidate = model_config["evaluation_candidates"][model_key]
    endpoint = candidate["endpoint"]
    model_origin = _external_origin(endpoint)
    supabase_url = os.environ.get("SCAM_RADAR_SUPABASE_URL", "").rstrip("/")
    supabase_origin = _external_origin(supabase_url)
    service_key = os.environ.get("SCAM_RADAR_SUPABASE_SERVICE_KEY", "")
    api_key = os.environ.get("SCAM_RADAR_MODEL_API_KEY", "")
    if not service_key or not api_key:
        raise RuntimeError("batch_credentials_missing")
    provider = HttpModelProvider(
        root=root,
        transport=BoundedHttpTransport(
            allowed_origins={model_origin},
            local_only=False,
            external_enabled=True,
            max_requests=max(1, settings.max_ai_calls_per_run),
            min_interval=0,
        ),
        endpoint=endpoint,
        model=candidate["model"],
        enable_thinking=candidate.get("enable_thinking"),
        protocol=candidate["protocol"],
        api_key=api_key,
        max_calls=settings.max_ai_calls_per_run,
        input_char_limit=10000,
    )
    store = RpcStore(
        transport=BoundedHttpTransport(
            allowed_origins={supabase_origin},
            local_only=False,
            external_enabled=True,
            max_requests=250,
            min_interval=0,
        ),
        base_url=supabase_url,
        token=service_key,
    )

    def collector_factory(source: dict[str, Any]) -> SourceCollector:
        limits = source["limits"]
        origin = _external_origin(source["collector"]["entry_url"])
        transport = BoundedHttpTransport(
            allowed_origins={origin},
            local_only=False,
            external_enabled=True,
            max_requests=min(250, 3 * int(limits["max_items_per_run"]) + 3),
            min_interval=int(limits["min_request_interval_ms"]) / 1000,
        )
        return SourceCollector(source, transport, user_agent="ScamRadar/0.1")

    commit_sha = (
        os.environ.get("GITHUB_SHA")
        or subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    result = DurablePipeline(
        store=store,
        provider=provider,
        policy=load_publication_policy(root / "config/publication-policy-v0.1.yaml"),
        collector_factory=collector_factory,
        max_items=settings.max_items_per_run,
        max_items_per_source=settings.max_items_per_source,
    ).run(
        sources=selected,
        commit_sha=commit_sha,
        registry_hash=registry.content_hash,
        behavior_hash=_behavior_hash(root),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["outcome"] == "success" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scam-radar")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("validate-registry")
    subcommands.add_parser("collect-dry-run")
    demo = subcommands.add_parser("demo")
    demo.add_argument("--output", type=Path, default=Path("work/release"))
    batch = subcommands.add_parser("run-batch")
    batch.add_argument("--source-key", default="all")
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
    if args.command == "run-batch":
        return run_batch(root, args.source_key)
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
