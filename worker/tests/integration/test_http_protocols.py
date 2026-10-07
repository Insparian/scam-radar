from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from scam_radar.collectors.http import BoundedHttpTransport, TransportError
from scam_radar.llm.budget import AttemptBudget
from scam_radar.llm.http_provider import HttpModelProvider


@pytest.fixture
def protocol_server() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    received: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "https://example.invalid/")
                self.end_headers()
                return
            if self.path == "/retry" and not received:
                received.append({"retry": True})
                self.send_response(429)
                self.send_header("Retry-After", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"local-source")

        def do_POST(self) -> None:
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            result = {
                "relevant": True,
                "elderly_relevance": "high",
                "category": "financial_scam",
                "confidence": 0.9,
                "reason": "synthetic",
            }
            content = json.dumps(result)
            if self.path == "/malformed" and len(received) == 1:
                content = "not json"
            if self.path == "/gemini":
                body = {
                    "candidates": [
                        {"finishReason": "STOP", "content": {"parts": [{"text": content}]}}
                    ]
                }
            else:
                body = {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_http_limits_retry_redirect(protocol_server: tuple[str, list[dict[str, Any]]]) -> None:
    origin, received = protocol_server
    transport = BoundedHttpTransport(allowed_origins={origin}, min_interval=0)
    assert (
        transport.get(origin + "/retry", timeout_seconds=1, max_bytes=100).body == b"local-source"
    )
    assert len(received) == 1 and transport.requests == 2
    with pytest.raises(TransportError, match="http_302"):
        transport.get(origin + "/redirect", timeout_seconds=1, max_bytes=100)
    with pytest.raises(TransportError, match="response_too_large"):
        transport.get(origin + "/large", timeout_seconds=1, max_bytes=2)
    with pytest.raises(TransportError, match="destination_not_approved"):
        transport.get("https://example.invalid", timeout_seconds=1, max_bytes=100)


@pytest.mark.parametrize(
    "protocol,path", [("openai", "/chat"), ("gemini", "/gemini"), ("openai", "/malformed")]
)
def test_real_model_protocol_and_caps(
    repository_root: Path,
    protocol_server: tuple[str, list[dict[str, Any]]],
    protocol: Any,
    path: str,
) -> None:
    origin, received = protocol_server
    provider = HttpModelProvider(
        root=repository_root,
        transport=BoundedHttpTransport(allowed_origins={origin}, min_interval=0),
        endpoint=origin + path,
        model="local-protocol-model",
        protocol=protocol,
        max_calls=2,
    )
    assert provider.classify("synthetic", "联系电话13812345678").relevant
    assert "13812345678" not in json.dumps(received, ensure_ascii=False)
    while provider.calls < 2:
        provider.classify("synthetic", "test")
    with pytest.raises(RuntimeError, match="model_call_budget_exhausted"):
        provider.classify("synthetic", "test")
    assert len(received) == 2


def test_eval_budget_counts_failed_retry_and_denies_before_network(
    repository_root: Path, protocol_server: tuple[str, list[dict[str, Any]]]
) -> None:
    origin, received = protocol_server
    budget = AttemptBudget.from_strings(
        max_attempts=2,
        max_spend_usd="1",
        input_usd_per_million="0.01",
        output_usd_per_million="0.01",
    )
    provider = HttpModelProvider(
        root=repository_root,
        transport=BoundedHttpTransport(allowed_origins={origin}, min_interval=0),
        endpoint=origin + "/malformed",
        model="local-protocol-model",
        protocol="openai",
        max_calls=2,
        before_attempt=budget.reserve,
    )
    assert provider.classify("synthetic", "合成风险提醒").relevant
    assert provider.calls == budget.attempts == len(received) == 2
    assert budget.reserved_usd > 0

    denied = AttemptBudget.from_strings(
        max_attempts=2,
        max_spend_usd="0.000001",
        input_usd_per_million="1",
        output_usd_per_million="1",
    )
    blocked = HttpModelProvider(
        root=repository_root,
        transport=BoundedHttpTransport(allowed_origins={origin}, min_interval=0),
        endpoint=origin + "/chat",
        model="local-protocol-model",
        protocol="openai",
        max_calls=2,
        before_attempt=denied.reserve,
    )
    with pytest.raises(RuntimeError, match="eval_spend_budget_exhausted"):
        blocked.classify("synthetic", "合成风险提醒")
    assert blocked.calls == denied.attempts == 0
    assert len(received) == 2


def test_free_eval_counts_retries_and_zero_cap_blocks_paid_request(
    repository_root: Path, protocol_server: tuple[str, list[dict[str, Any]]]
) -> None:
    origin, received = protocol_server
    budget = AttemptBudget.from_strings(
        max_attempts=2,
        max_spend_usd="0",
        input_usd_per_million="0",
        output_usd_per_million="0",
    )
    provider = HttpModelProvider(
        root=repository_root,
        transport=BoundedHttpTransport(allowed_origins={origin}, min_interval=0),
        endpoint=origin + "/malformed",
        model="local-free-model",
        protocol="openai",
        max_calls=3,
        before_attempt=budget.reserve,
    )
    assert provider.classify("synthetic", "合成风险提醒").relevant
    assert provider.calls == budget.attempts == len(received) == 2
    assert budget.reserved_usd == 0
    with pytest.raises(RuntimeError, match="eval_call_budget_exhausted"):
        provider.classify("synthetic", "合成风险提醒")
    for input_price, output_price in (("0.01", "0"), ("0", "0.01")):
        denied = AttemptBudget.from_strings(
            max_attempts=2,
            max_spend_usd="0",
            input_usd_per_million=input_price,
            output_usd_per_million=output_price,
        )
        paid = HttpModelProvider(
            root=repository_root,
            transport=BoundedHttpTransport(allowed_origins={origin}, min_interval=0),
            endpoint=origin + "/chat",
            model="local-paid-model",
            protocol="openai",
            max_calls=2,
            before_attempt=denied.reserve,
        )
        with pytest.raises(RuntimeError, match="eval_spend_budget_exhausted"):
            paid.classify("synthetic", "合成风险提醒")
        assert paid.calls == denied.attempts == 0
    assert len(received) == 2


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "-Infinity", "invalid"])
@pytest.mark.parametrize(
    "field", ["max_spend_usd", "input_usd_per_million", "output_usd_per_million"]
)
def test_free_eval_rejects_invalid_amounts(value: str, field: str) -> None:
    amounts = dict(max_spend_usd="0", input_usd_per_million="0", output_usd_per_million="0")
    amounts[field] = value
    with pytest.raises(ValueError, match="invalid_eval_"):
        AttemptBudget.from_strings(max_attempts=2, **amounts)


@pytest.mark.parametrize("free", [False, True])
def test_dormant_live_eval_entry_counts_local_failure_and_refuses_activation(
    repository_root: Path,
    protocol_server: tuple[str, list[dict[str, Any]]],
    tmp_path: Path,
    free: bool,
) -> None:
    import os
    import subprocess
    import sys

    origin, received = protocol_server
    cases = tmp_path / "human-labels.json"
    cases.write_text(
        json.dumps(
            [
                {
                    "id": "synthetic-risk-case",
                    "text": "合成风险提醒",
                    "expected_relevant": True,
                    "expected_category": "financial_scam",
                    "expected_actions": [],
                }
            ]
        )
    )
    pricing = tmp_path / "pricing.json"
    pricing.write_text(
        json.dumps(
            {
                "candidate": "glm",
                "input_usd_per_million": "0" if free else "0.01",
                "output_usd_per_million": "0" if free else "0.01",
            }
        )
    )
    report = tmp_path / "report.json"
    command = [
        sys.executable,
        str(repository_root / "evals/run_live_eval.py"),
        "--candidate",
        "glm",
        "--cases",
        str(cases),
        "--pricing",
        str(pricing),
        "--output",
        str(report),
        "--max-calls",
        "3",
        "--max-spend-usd",
        "0" if free else "1",
    ]
    local = subprocess.run(
        [*command, "--local-endpoint", origin + "/chat"], capture_output=True, check=False
    )
    assert local.returncode == 1
    contents = json.loads(report.read_text())
    assert contents["calls"] == len(received) == 3
    assert contents["failed_cases"] == 1
    assert contents["scope"] == "local_protocol_only"
    assert contents["launch_qualified"] is False
    assert (float(contents["reserved_spend_upper_bound_usd"]) == 0) is free
    assert "合成风险提醒" not in report.read_text()
    blocked = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "SCAM_RADAR_LIVE_EVAL_APPROVED": "false",
            "SCAM_RADAR_LIVE_ACTIVATION_APPROVED": "false",
        },
    )
    assert blocked.returncode != 0
    assert b"live_eval_activation_required" in blocked.stderr
    assert len(received) == 3


def test_configured_eval_entry_all_candidates(
    repository_root: Path, protocol_server: tuple[str, list[dict[str, Any]]], tmp_path: Path
) -> None:
    import subprocess
    import sys

    origin, _ = protocol_server
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps([{"id": "synthetic-case", "text": "合成风险提醒", "expected_relevant": True}])
    )
    hashes = set()
    for candidate in ("glm", "qwen", "gemini"):
        output = tmp_path / f"{candidate}.json"
        subprocess.run(
            [
                sys.executable,
                str(repository_root / "evals/run_provider_protocol_eval.py"),
                "--candidate",
                candidate,
                "--local-endpoint",
                origin + ("/gemini" if candidate == "gemini" else "/chat"),
                "--cases",
                str(cases),
                "--output",
                str(output),
            ],
            check=True,
            capture_output=True,
        )
        report = json.loads(output.read_text())
        assert report["launch_qualified"] is False
        assert report["scope"] == "local_protocol_only"
        assert report["calls"] == 1
        assert report["results"][0]["matched"] is True
        assert "合成风险提醒" not in output.read_text()
        hashes.add(report["dataset_sha256"])
    assert len(hashes) == 1


@pytest.mark.parametrize("confirmed,has_limit", [(True, True), (False, True), (True, False)])
def test_free_live_eval_requires_account_confirmation_before_provider(
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    confirmed: bool,
    has_limit: bool,
) -> None:
    import argparse
    import runpy
    from datetime import UTC, datetime

    entry = runpy.run_path(str(repository_root / "evals/run_live_eval.py"))
    run = entry["run"]
    monkeypatch.setitem(run.__globals__, "ROOT", tmp_path)
    (tmp_path / "work").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config/models.yaml").write_text(
        "evaluation_candidates:\n  gemini:\n    endpoint: https://model.example.invalid\n"
    )
    cases = tmp_path / "work/cases.json"
    cases.write_text(
        json.dumps([dict(id="synthetic-case", text="synthetic", expected_relevant=False)])
    )
    pricing = tmp_path / "work/pricing.json"
    today = datetime.now(UTC).date().isoformat()
    pricing.write_text(
        json.dumps(
            dict(
                candidate="gemini",
                input_usd_per_million="0",
                output_usd_per_million="0",
                account_hard_limit_usd="0",
                free_tier_only=confirmed,
                price_verified_at=today,
                quota_verified_at=today,
                account_hard_limit_verified_at=today,
                region="synthetic",
                approved_region="synthetic",
            )
        )
    )
    if not has_limit:
        record = json.loads(pricing.read_text())
        record.pop("account_hard_limit_usd")
        pricing.write_text(json.dumps(record))
    monkeypatch.setenv("SCAM_RADAR_LIVE_ACTIVATION_APPROVED", "true")
    monkeypatch.setenv("SCAM_RADAR_LIVE_EVAL_APPROVED", "true")

    def stop_before_network(*args: object, **kwargs: Any) -> None:
        assert kwargs["budget"].max_spend_usd == 0
        assert kwargs["budget"].attempts == 0
        raise RuntimeError("verified_budget_before_network")

    monkeypatch.setitem(run.__globals__, "_provider", stop_before_network)
    args = argparse.Namespace(
        candidate="gemini",
        cases=cases,
        pricing=pricing,
        output=tmp_path / "work/report.json",
        local_endpoint=None,
        confirmation=entry["CONFIRMATION"],
        max_calls=2,
        max_spend_usd="0",
    )
    expected = (
        "verified_budget_before_network"
        if confirmed
        else "eval_free_tier_only_confirmation_required"
    )
    if not has_limit:
        expected = "account_hard_limit_usd"
    with pytest.raises((RuntimeError, ValueError, KeyError), match=expected):
        run(args)


def test_qwen_config_sends_non_thinking_json_and_isolates_cache(
    repository_root: Path, protocol_server: tuple[str, list[dict[str, Any]]]
) -> None:
    from scam_radar.llm.configured import evaluation_provider

    origin, received = protocol_server
    selected = evaluation_provider(repository_root, "qwen", local_endpoint=origin + "/chat")
    assert selected.classify("synthetic", "合成风险提醒").relevant
    assert received[0]["enable_thinking"] is False
    assert received[0]["response_format"] == {"type": "json_object"}
    assert received[0]["stream"] is False
    default = HttpModelProvider(
        root=repository_root,
        transport=BoundedHttpTransport(allowed_origins={origin}, min_interval=0),
        endpoint=origin + "/chat",
        model=selected.model,
        protocol="openai",
    )
    assert default.fingerprint("relevance-v1", "synthetic") != selected.fingerprint(
        "relevance-v1", "synthetic"
    )
    assert default.classify("synthetic", "合成风险提醒").relevant
    assert "enable_thinking" not in received[1]
