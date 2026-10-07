"""Run the real collector/model/RPC chain against disposable local Supabase."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from scam_radar.collectors.base import FetchResult
from scam_radar.collectors.http import BoundedHttpTransport, TransportError
from scam_radar.collectors.source import SourceCollector
from scam_radar.durable import DurablePipeline
from scam_radar.llm.http_provider import HttpModelProvider
from scam_radar.policy.engine import load_publication_policy
from scam_radar.storage.public_export import map_database_release
from scam_radar.storage.rpc import RpcStore

ROOT = Path(__file__).resolve().parents[3]
DOCKER = (
    os.getenv("DOCKER_BIN")
    or shutil.which("docker")
    or "/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/docker"
)
DB_CONTAINER = os.getenv("SUPABASE_DB_CONTAINER", "supabase_db_scam-radar-offline")
LOCAL_PROJECT = DB_CONTAINER.removeprefix("supabase_db_")
LOCAL_API = os.getenv("SCAM_RADAR_LOCAL_API_URL", "http://127.0.0.1:54321")


def local_keys() -> dict[str, str]:
    result = subprocess.run(
        [DOCKER, "inspect", f"supabase_studio_{LOCAL_PROJECT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    environment = json.loads(result.stdout)[0]["Config"]["Env"]
    values = dict(item.split("=", 1) for item in environment if "=" in item)
    keys = {
        "service": values.get("SUPABASE_SERVICE_KEY", ""),
        "anon": values.get("SUPABASE_ANON_KEY", ""),
    }
    if not all(keys.values()):
        raise RuntimeError("isolated_auth_keys_missing")
    return keys


def _post_json(
    transport: BoundedHttpTransport,
    url: str,
    payload: dict[str, Any],
    *,
    apikey: str,
    bearer: str,
) -> Any:
    response = transport.request(
        url,
        method="POST",
        body=json.dumps(payload, ensure_ascii=False).encode(),
        headers={
            "Content-Type": "application/json",
            "apikey": apikey,
            "Authorization": f"Bearer {bearer}",
        },
        retries=0,
    )
    return json.loads(response.body) if response.body else None


def review_in_browser(
    email: str, password: str, anon_key: str, *, script: str = "check-review-browser.mjs"
) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    environment = {
        **os.environ,
        "NEXT_PUBLIC_SUPABASE_URL": LOCAL_API,
        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY": anon_key,
        "NEXT_TELEMETRY_DISABLED": "1",
    }
    server_log = ROOT / "work/launch-readiness/joined-review-next.log"
    server_log.parent.mkdir(parents=True, exist_ok=True)
    with server_log.open("w") as output:
        server = subprocess.Popen(
            ["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(port)],
            cwd=ROOT / "web",
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            for _ in range(160):
                if server.poll() is not None:
                    raise RuntimeError("local_reviewer_web_server_exited")
                try:
                    with urlopen(base_url + "/admin/login/", timeout=2) as response:
                        if response.status == 200:
                            break
                except (OSError, URLError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("local_reviewer_web_server_timeout")
            browser_env = {
                **os.environ,
                "SCAM_RADAR_REVIEW_BASE_URL": base_url,
                "SCAM_RADAR_REVIEW_EMAIL": email,
                "SCAM_RADAR_REVIEW_PASSWORD": password,
            }
            subprocess.run(
                ["node", f"scripts/{script}"],
                cwd=ROOT / "web",
                env=browser_env,
                check=True,
            )
        finally:
            with suppress(ProcessLookupError):
                os.killpg(server.pid, signal.SIGTERM)
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGKILL)
                server.wait(timeout=5)


def review_and_build(
    source_key: str, store: RpcStore, keys: dict[str, str], *, browser_review: bool = False
) -> None:
    auth_http = BoundedHttpTransport(
        allowed_origins={LOCAL_API},
        min_interval=0,
        max_requests=30,
    )
    try:
        _post_json(
            auth_http,
            LOCAL_API + "/auth/v1/signup",
            {
                "email": f"unapproved-{uuid4().hex[:12]}@example.invalid",
                "password": secrets.token_urlsafe(24),
            },
            apikey=keys["anon"],
            bearer=keys["anon"],
        )
    except TransportError as exc:
        if str(exc) not in {"http_400", "http_403", "http_422"}:
            raise
    else:
        raise AssertionError("local_public_reviewer_signup_enabled")
    email = f"local-reviewer-{uuid4().hex[:12]}@example.invalid"
    password = secrets.token_urlsafe(24)
    created = _post_json(
        auth_http,
        LOCAL_API + "/auth/v1/admin/users",
        {"email": email, "password": password, "email_confirm": True},
        apikey=keys["service"],
        bearer=keys["service"],
    )
    reviewer_id = str(UUID(created["id"]))
    sql_scalar(
        "insert into public.admin_users(user_id,role,enabled) values "
        f"('{reviewer_id}','reviewer',true) returning user_id"
    )
    try:
        session = _post_json(
            auth_http,
            LOCAL_API + "/auth/v1/token?grant_type=password",
            {"email": email, "password": password},
            apikey=keys["anon"],
            bearer=keys["anon"],
        )
    except TransportError as exc:
        if not LOCAL_API.startswith("http://127.0.0.1:"):
            raise
        diagnostic = Request(
            LOCAL_API + "/auth/v1/token?grant_type=password",
            data=json.dumps({"email": email, "password": password}).encode(),
            headers={"Content-Type": "application/json", "apikey": keys["anon"]},
            method="POST",
        )
        try:
            urlopen(diagnostic, timeout=5)
        except HTTPError as error:
            body = json.loads(error.read())
            code = body.get("error_code", "unknown")
            raise RuntimeError(f"local_auth_login_{code}") from exc
        raise
    access_token = session["access_token"]
    bootstrap = _post_json(
        auth_http,
        LOCAL_API + "/rest/v1/rpc/get_reviewer_bootstrap",
        {},
        apikey=keys["anon"],
        bearer=access_token,
    )
    if bootstrap["reviewer"]["user_id"] != reviewer_id:
        raise AssertionError("local_auth_reviewer_identity_mismatch")
    target = next(
        item
        for item in bootstrap["queue"]
        if item.get("pattern", {}).get("slug", "").startswith(f"source-{source_key}-")
    )
    if (
        target["policy"]["decision_outcome"] != "review_required"
        or target["pattern"]["lifecycle_status"] != "review_ready"
    ):
        raise AssertionError("local_candidate_not_reviewable")
    draft = target["pattern"]["draft_revision"]
    evidence_ids = [item["id"] for item in target["evidence"]]
    approval = {
        "p_policy_decision_id": target["policy"]["id"],
        "p_review_item_id": target["id"],
        "p_draft_revision_id": draft["id"],
        "p_expected_row_version": target["pattern"]["row_version"],
        "p_expected_candidate_hash": target["candidate_hash"],
        "p_expected_content_hash": draft["content_hash"],
        "p_accepted_evidence_ids": evidence_ids,
        "p_rejected_evidence_ids": [],
        "p_decision_note": "隔离本地合成数据人工审核演练",
    }
    try:
        store.call("confirm_policy_publication", approval)
    except TransportError:
        pass
    else:
        raise AssertionError("service_role_impersonated_human_approval")
    fixture = next(
        item for item in bootstrap["queue"] if item["id"] == "a0000000-0000-4000-8000-000000000001"
    )
    if browser_review:
        review_in_browser(email, password, keys["anon"])
        statuses = sql_scalar(
            "select (select status from public.review_items where id='"
            + target["id"]
            + "') || ':' || (select status from public.review_items where id='"
            + fixture["id"]
            + "')"
        )
        if statuses != "approved:rejected":
            raise AssertionError("local_browser_review_decisions_missing")
    else:
        _post_json(
            auth_http,
            LOCAL_API + "/rest/v1/rpc/reject_review_item",
            {
                "p_review_item_id": fixture["id"],
                "p_expected_candidate_hash": fixture["candidate_hash"],
                "p_decision_note": "隔离演练：种子候选不进入发布",
            },
            apikey=keys["anon"],
            bearer=access_token,
        )
        approved_id = _post_json(
            auth_http,
            LOCAL_API + "/rest/v1/rpc/confirm_policy_publication",
            approval,
            apikey=keys["anon"],
            bearer=access_token,
        )
        if approved_id != draft["id"]:
            raise AssertionError("local_human_approval_receipt_mismatch")
    release_id = store.call("prepare_public_release", {"p_expected_previous_release_id": None})
    release_id = str(UUID(release_id))
    exported = store.call("export_public_release", {"p_release_id": release_id})
    mapped = map_database_release(exported, release_id)
    if len(mapped["patterns"]) != 1 or mapped["patterns"][0]["slug"] != target["pattern"]["slug"]:
        raise AssertionError("local_exact_release_mapping_failed")
    output = ROOT / "work/launch-readiness/joined-e2e" / release_id
    output.mkdir(parents=True, exist_ok=False)
    release_path = output / "public-release.json"
    release_path.write_text(json.dumps(mapped, ensure_ascii=False, indent=2) + "\n")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_public_release.py"),
            "--release",
            str(release_path),
            "--release-id",
            release_id,
            "--destination",
            str(output / "site"),
        ],
        cwd=ROOT,
        check=True,
    )
    print(
        "GREEN local Auth login → reviewer rejection and human approval → "
        "exact immutable release → static site build; service approval rejected"
    )


class LocalSourceTransport:
    def __init__(self, origin: str) -> None:
        self.origin = origin
        self.http = BoundedHttpTransport(
            allowed_origins={origin},
            min_interval=0,
            max_requests=30,
        )

    def get(self, url: str, *, timeout_seconds: int, max_bytes: int) -> FetchResult:
        path = "/" + url.split("/", 3)[3]
        result = self.http.get(
            self.origin + path, timeout_seconds=timeout_seconds, max_bytes=max_bytes
        )
        return FetchResult(
            url=url,
            body=result.body,
            content_type=result.content_type,
            status_code=result.status_code,
            etag=result.etag,
            last_modified=result.last_modified,
        )


@contextmanager
def protocol_server(*, existing_update: bool = False) -> Iterator[tuple[str, dict[str, int]]]:
    calls = {"model": 0, "source": 0, "relevance": 0, "extraction": 0, "comparison": 0}
    article = (
        "合成来电索取验证码并要求转账。\n"
        "合成补贴来电骗局\nimpersonation\nreported_case\nconfirmed_scam\n"
        "警方通报的诈骗案件\nphone_call\n养老补贴\n索取验证码\n"
        "挂断并拨打官方电话核实\n2026-09-18T00:00:00.000000Z"
    )
    extraction = {
        "suspected_pattern_name": "合成补贴来电骗局",
        "target_population": [],
        "contact_channels": ["phone_call"],
        "hook": "养老补贴",
        "promise": None,
        "pressure_tactics": [],
        "requested_actions": ["索取验证码"],
        "case_date": "2026-09-18",
        "money_path": None,
        "credential_requests": [],
        "technology_used": [],
        "regions": [],
        "source_claim_type": "official_case",
        "official_status": "reported_case",
        "warning_signs": ["索取验证码"],
        "recommended_actions": ["挂断并拨打官方电话核实"],
        "supporting_spans": [
            {
                "field_path": field_path,
                "start": article.index(value),
                "end": article.index(value) + len(value),
                "excerpt": value,
            }
            for field_path, value in (
                ("canonical_name", "合成补贴来电骗局"),
                ("one_sentence_summary", "合成来电索取验证码并要求转账"),
                ("contact_channels[1]", "phone_call"),
                ("hooks[1]", "养老补贴"),
                ("warning_signs[1]", "索取验证码"),
                ("requested_actions[1]", "索取验证码"),
                ("what_to_do[1]", "挂断并拨打官方电话核实"),
            )
        ],
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            calls["source"] += 1
            if self.path == "/robots.txt":
                body, content_type = b"User-agent: *\nAllow: /\n", "text/plain"
            elif self.path == "/feed.xml":
                item_name = "local-update" if existing_update else "local-candidate"
                body = (
                    '<rss version="2.0"><channel><title>Local synthetic</title>'
                    f"<item><guid>{item_name}</guid><title>Synthetic</title>"
                    f"<link>https://alerts.example.invalid/article-{item_name}</link>"
                    "<pubDate>Fri, 18 Sep 2026 00:00:00 GMT</pubDate>"
                    "</item></channel></rss>"
                ).encode()
                content_type = "application/rss+xml"
            elif self.path in {"/article-local-candidate", "/article-local-update"}:
                body = (
                    "<html><h1>Synthetic candidate</h1><article>"
                    + "".join(f"<p>{line}</p>" for line in article.splitlines())
                    + "</article></html>"
                ).encode()
                content_type = "text/html"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/model":
                self.send_error(404)
                return
            calls["model"] += 1
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            schema_prompt = payload["messages"][0]["content"]
            if '"suspected_pattern_name"' in schema_prompt:
                calls["extraction"] += 1
                result: dict[str, Any] = extraction
            elif '"same_pattern"' in schema_prompt:
                calls["comparison"] += 1
                result = {
                    "same_pattern": existing_update,
                    "confidence": 0.9,
                    "reason_codes": ["same_hook"] if existing_update else ["insufficient_features"],
                    "material_change": False,
                    "changes": ["none"],
                }
            else:
                calls["relevance"] += 1
                result = {
                    "relevant": True,
                    "elderly_relevance": "high",
                    "category": "impersonation",
                    "confidence": 0.9,
                    "reason": "synthetic_local_protocol",
                }
            content = json.dumps(result, ensure_ascii=False)
            if not existing_update and calls["extraction"] in {1, 2}:
                content = "invalid-local-response"
            body = json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": content},
                        }
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 10},
                },
                ensure_ascii=False,
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def sql_scalar(query: str) -> str:
    result = subprocess.run(
        [
            DOCKER,
            "exec",
            DB_CONTAINER,
            "psql",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main(*, full_review: bool = False, browser_review: bool = False) -> int:
    source_key = f"local-e2e-{uuid4().hex[:10]}"
    source = {
        "key": source_key,
        "display_name": "隔离本地合成警方来源",
        "publisher_group": source_key,
        "source_type": "police",
        "authority_tier": "A1",
        "enabled": True,
        "collector": {"type": "rss", "entry_url": "https://alerts.example.invalid/feed.xml"},
        "policy": {
            "collection_allowed": True,
            "reviewed_at": "2026-09-20",
            "robots_url": "https://alerts.example.invalid/robots.txt",
        },
        "parser": {"config": {"title_selector": "h1", "body_selector": "article"}},
        "limits": {"max_items_per_run": 5, "timeout_seconds": 5},
    }
    keys = local_keys()
    with protocol_server() as (origin, calls):
        store = RpcStore(
            transport=BoundedHttpTransport(
                allowed_origins={LOCAL_API},
                min_interval=0,
                max_requests=250,
            ),
            base_url=LOCAL_API,
            token=keys["service"],
        )
        provider = HttpModelProvider(
            root=ROOT,
            transport=BoundedHttpTransport(
                allowed_origins={origin},
                min_interval=0,
                max_requests=20,
            ),
            endpoint=origin + "/model",
            model="local-protocol-model",
            protocol="openai",
            max_calls=10,
        )
        pipeline = DurablePipeline(
            store=store,
            provider=provider,
            policy=load_publication_policy(ROOT / "config/publication-policy-v0.1.yaml"),
            collector_factory=lambda reviewed: SourceCollector(
                reviewed, LocalSourceTransport(origin), user_agent="ScamRadarLocalTest/1"
            ),
            max_items=5,
            max_items_per_source=5,
        )
        parameters = {
            "sources": [source],
            "commit_sha": "a" * 40,
            "registry_hash": "b" * 64,
            "behavior_hash": "c" * 64,
        }
        first = pipeline.run(**parameters)
        if first["outcome"] != "degraded" or first["counts"].get("analysis_failures") != 1:
            raise AssertionError(
                f"local_pipeline_first_run_failed:{first['outcome']}:{first['counts']}"
            )
        first_error = sql_scalar(
            "select version.last_error || ':' || run.error_summary "
            "from public.source_item_versions as version "
            "join public.source_items as item on item.id=version.source_item_id "
            "join public.sources as source on source.id=item.source_id "
            f"join public.pipeline_runs as run on run.id='{first['run_id']}' "
            f"where source.source_key='{source_key}' and version.processing_status='error'"
        )
        if first_error != "extraction_model_failed:extraction_model_failed":
            raise AssertionError(f"model_failure_stage_not_recorded:{first_error}")
        failed_cursor = sql_scalar(
            "select coalesce(state.cursor_value,'<empty>') "
            "from public.source_states as state "
            "join public.sources as source on source.id=state.source_id "
            f"where source.source_key='{source_key}'"
        )
        if failed_cursor != "<empty>":
            raise AssertionError("failed_analysis_advanced_source_cursor")
        second = pipeline.run(**parameters)
        if second["outcome"] != "success" or second["counts"].get("review_items") != 1:
            raise AssertionError("local_pipeline_recovery_failed")
        # The first extraction consumes its two configured malformed-response
        # retries; recovery reuses relevance and succeeds on one extraction.
        if calls != {"model": 4, "source": 6, "relevance": 1, "extraction": 3, "comparison": 0}:
            raise AssertionError(f"recovery_model_stage_counts_changed:{calls}")
        calls_before_duplicate = calls.copy()
        third = pipeline.run(**parameters)
        if third["outcome"] != "success" or third["counts"].get("review_items", 0) != 0:
            raise AssertionError("local_pipeline_duplicate_run_failed")
        if calls["model"] != calls_before_duplicate["model"]:
            raise AssertionError("duplicate_run_called_model")
        counts = sql_scalar(
            "select count(*) || ':' || count(distinct candidate.pattern_id) "
            "from public.source_version_candidates as candidate "
            "join public.source_item_versions as version "
            "on version.id=candidate.source_item_version_id "
            "join public.source_items as item on item.id=version.source_item_id "
            "join public.sources as source on source.id=item.source_id "
            f"where source.source_key='{source_key}'"
        )
        if counts != "1:1":
            raise AssertionError("local_pipeline_candidate_duplicate")
        print(
            "RED→GREEN local model failure retained cursor; resumed from cached relevance, "
            "then real DB draft/evidence/Heat/Policy/review; third run no duplicate"
        )
        if full_review:
            review_and_build(source_key, store, keys, browser_review=browser_review)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-review", action="store_true")
    parser.add_argument("--browser-review", action="store_true")
    options = parser.parse_args()
    if options.browser_review and not options.full_review:
        parser.error("--browser-review requires --full-review")
    raise SystemExit(main(full_review=options.full_review, browser_review=options.browser_review))
