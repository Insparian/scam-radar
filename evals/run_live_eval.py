"""Dormant, bounded model evaluation; local protocol is the only default mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker/src"))

from scam_radar.collectors.http import BoundedHttpTransport, TransportError
from scam_radar.llm.budget import AttemptBudget
from scam_radar.llm.http_provider import HttpModelProvider

CONFIRMATION = "EVALUATE ONE REVIEWED MODEL WITH BOUNDED SPEND"
MAX_CASES = 50


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _percentile(values: list[int], proportion: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * proportion))]


def _verified_date(value: Any, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name}_required")
    reviewed = date.fromisoformat(value)
    if (
        reviewed > datetime.now(UTC).date()
        or (datetime.now(UTC).date() - reviewed).days > 30
    ):
        raise ValueError(f"{name}_stale")


def _cases(path: Path) -> tuple[bytes, list[dict[str, Any]]]:
    raw = path.read_bytes()
    if len(raw) > 600_000:
        raise ValueError("eval_dataset_too_large")
    cases = json.loads(raw)
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("eval_case_limit")
    ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise TypeError("invalid_eval_case")
        case_id, source = case.get("id"), case.get("text")
        if not isinstance(case_id, str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", case_id
        ):
            raise ValueError("invalid_eval_case_id")
        if case_id in ids:
            raise ValueError("duplicate_eval_case_id")
        ids.add(case_id)
        if not isinstance(source, str) or not 1 <= len(source) <= 10_000:
            raise ValueError("invalid_eval_case_text")
        if not isinstance(case.get("expected_relevant"), bool):
            raise TypeError("missing_human_relevance_label")
        if case.get("expected_relevant"):
            if not isinstance(case.get("expected_category"), str):
                raise ValueError("missing_human_category_label")
            if not isinstance(case.get("expected_actions"), list) or not all(
                isinstance(action, str) for action in case["expected_actions"]
            ):
                raise ValueError("missing_human_action_labels")
        candidates = case.get("candidate_revisions", [])
        if (
            not isinstance(candidates, list)
            or len(candidates) > 10
            or not all(isinstance(candidate, dict) for candidate in candidates)
        ):
            raise ValueError("invalid_eval_candidates")
        if candidates and not isinstance(case.get("expected_same_pattern"), bool):
            raise ValueError("missing_human_pattern_label")
        if candidates and not isinstance(case.get("expected_material_change"), bool):
            raise ValueError("missing_human_change_label")
    return raw, cases


def _provider(
    candidate: str, endpoint: str, *, live: bool, budget: AttemptBudget
) -> HttpModelProvider:
    config = yaml.safe_load((ROOT / "config/models.yaml").read_text())
    selected = config["evaluation_candidates"][candidate]
    configured = selected["endpoint"]
    if live:
        if not selected.get("price_verified") or endpoint != configured:
            raise ValueError("reviewed_model_price_and_endpoint_required")
        api_key = os.environ.get("SCAM_RADAR_EVAL_API_KEY", "")
        if not api_key:
            raise ValueError("live_eval_key_required")
    else:
        api_key = ""
    parts = urlsplit(endpoint)
    if live:
        if parts.scheme != "https" or parts.username or parts.password:
            raise ValueError("live_eval_https_required")
    elif parts.scheme != "http" or parts.hostname != "127.0.0.1":
        raise ValueError("local_eval_loopback_required")
    transport = BoundedHttpTransport(
        allowed_origins={f"{parts.scheme}://{parts.netloc}"},
        local_only=not live,
        external_enabled=live,
        max_requests=budget.max_attempts,
        min_interval=0,
    )
    return HttpModelProvider(
        root=ROOT,
        transport=transport,
        endpoint=endpoint,
        model=selected["model"],
        protocol=selected["protocol"],
        api_key=api_key,
        max_calls=budget.max_attempts,
        before_attempt=budget.reserve,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    live = args.local_endpoint is None
    if live:
        if (
            os.environ.get("SCAM_RADAR_LIVE_ACTIVATION_APPROVED") != "true"
            or os.environ.get("SCAM_RADAR_LIVE_EVAL_APPROVED") != "true"
            or args.confirmation != CONFIRMATION
        ):
            raise ValueError("live_eval_activation_required")
        if not args.cases.resolve().is_relative_to(ROOT / "work"):
            raise ValueError("live_eval_cases_must_be_ignored_local_data")
        if not args.pricing.resolve().is_relative_to(
            ROOT / "work"
        ) or not args.output.resolve().is_relative_to(ROOT / "work"):
            raise ValueError("live_eval_files_must_be_ignored_local_data")
        if args.max_calls > 10 or Decimal(args.max_spend_usd) > Decimal(1):
            raise ValueError("live_eval_hard_limit_exceeded")
    raw, cases = _cases(args.cases)
    pricing = json.loads(args.pricing.read_text())
    if not isinstance(pricing, dict) or pricing.get("candidate") != args.candidate:
        raise ValueError("reviewed_eval_pricing_required")
    if live:
        _verified_date(pricing.get("price_verified_at"), "eval_price")
        _verified_date(pricing.get("quota_verified_at"), "eval_quota")
        _verified_date(
            pricing.get("account_hard_limit_verified_at"), "eval_account_limit"
        )
        if (
            not isinstance(pricing.get("region"), str)
            or not pricing["region"]
            or pricing["region"] != pricing.get("approved_region")
        ):
            raise ValueError("eval_region_not_approved")
        account_limit = Decimal(str(pricing.get("account_hard_limit_usd", "0")))
        if not Decimal(0) < account_limit <= Decimal(1):
            raise ValueError("eval_account_hard_limit_exceeded")
        if Decimal(args.max_spend_usd) > account_limit:
            raise ValueError("eval_spend_exceeds_account_limit")
    budget = AttemptBudget.from_strings(
        max_attempts=args.max_calls,
        max_spend_usd=args.max_spend_usd,
        input_usd_per_million=pricing["input_usd_per_million"],
        output_usd_per_million=pricing["output_usd_per_million"],
    )
    endpoint = (
        args.local_endpoint
        or yaml.safe_load((ROOT / "config/models.yaml").read_text())[
            "evaluation_candidates"
        ][args.candidate]["endpoint"]
    )
    provider = _provider(args.candidate, endpoint, live=live, budget=budget)
    results: list[dict[str, Any]] = []
    relevant_tp = relevant_fp = relevant_fn = 0
    category_hits = action_hits = action_total = 0
    pattern_tp = pattern_fp = pattern_fn = 0
    change_tp = change_fp = change_fn = 0
    latencies: list[int] = []
    for case in cases:
        started = time.monotonic()
        status = "valid"
        predicted_relevant = False
        category_match = False
        action_match_count = 0
        same_pattern = False
        material_change = False
        try:
            relevance = provider.classify(case["id"], case["text"])
            predicted_relevant = relevance.relevant
            if case["expected_relevant"] and relevance.relevant:
                category_match = relevance.category == case["expected_category"]
                extraction = provider.extract(case["id"], case["text"])
                action_match_count = sum(
                    action in extraction.recommended_actions
                    for action in case["expected_actions"]
                )
            if case.get("candidate_revisions"):
                comparison = provider.compare_patterns(
                    case["id"],
                    case["text"],
                    [
                        json.dumps(item, ensure_ascii=False)
                        for item in case["candidate_revisions"]
                    ],
                )
                same_pattern = comparison.same_pattern
                material_change = comparison.material_change
        except (ValueError, RuntimeError, TransportError, KeyError, TypeError) as error:
            status = (
                "budget_exhausted"
                if str(error)
                in {
                    "eval_call_budget_exhausted",
                    "eval_spend_budget_exhausted",
                    "model_call_budget_exhausted",
                }
                else "protocol_failed"
            )
        expected = case["expected_relevant"]
        relevant_tp += int(status == "valid" and predicted_relevant and expected)
        relevant_fp += int(status == "valid" and predicted_relevant and not expected)
        relevant_fn += int(expected and (status != "valid" or not predicted_relevant))
        category_hits += int(status == "valid" and category_match)
        action_hits += action_match_count if status == "valid" else 0
        action_total += len(case.get("expected_actions", []))
        if case.get("candidate_revisions"):
            match_expected = case["expected_same_pattern"]
            change_expected = case["expected_material_change"]
            pattern_tp += int(status == "valid" and same_pattern and match_expected)
            pattern_fp += int(status == "valid" and same_pattern and not match_expected)
            pattern_fn += int(
                match_expected and (status != "valid" or not same_pattern)
            )
            change_tp += int(status == "valid" and material_change and change_expected)
            change_fp += int(
                status == "valid" and material_change and not change_expected
            )
            change_fn += int(
                change_expected and (status != "valid" or not material_change)
            )
        elapsed_ms = round((time.monotonic() - started) * 1000)
        latencies.append(elapsed_ms)
        results.append({"id": case["id"], "status": status, "latency_ms": elapsed_ms})
    return {
        "scope": "live_shadow" if live else "local_protocol_only",
        "launch_qualified": False,
        "candidate": args.candidate,
        "model": provider.model,
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "cases": len(cases),
        "calls": provider.calls,
        "failed_cases": sum(item["status"] != "valid" for item in results),
        "reserved_spend_upper_bound_usd": str(budget.reserved_usd),
        "max_spend_usd": str(budget.max_spend_usd),
        "relevance_precision": _rate(relevant_tp, relevant_tp + relevant_fp),
        "relevance_recall": _rate(relevant_tp, relevant_tp + relevant_fn),
        "category_accuracy": _rate(
            category_hits, sum(case["expected_relevant"] for case in cases)
        ),
        "required_action_recall": _rate(action_hits, action_total),
        "pattern_match_precision": _rate(pattern_tp, pattern_tp + pattern_fp),
        "pattern_match_recall": _rate(pattern_tp, pattern_tp + pattern_fn),
        "material_change_precision": _rate(change_tp, change_tp + change_fp),
        "material_change_recall": _rate(change_tp, change_tp + change_fn),
        "latency_p50_ms": round(statistics.median(latencies)),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=["glm", "qwen", "gemini"], required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--pricing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-calls", type=int, required=True)
    parser.add_argument("--max-spend-usd", required=True)
    parser.add_argument("--local-endpoint")
    parser.add_argument("--confirmation")
    args = parser.parse_args()
    report = run(args)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(
        f"eval scope={report['scope']} cases={report['cases']} calls={report['calls']} "
        f"failed={report['failed_cases']} launch_qualified=false"
    )
    return 0 if report["failed_cases"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
