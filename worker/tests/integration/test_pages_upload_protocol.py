from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from scripts.deploy_public_release import artifact_hash
from scripts.pages_upload import CloudflarePages


def _artifact(root: Path, release_id: str) -> None:
    root.mkdir()
    (root / "index.html").write_text(release_id)
    (root / "404.html").write_text("missing")
    (root / "release.json").write_text(
        json.dumps(
            {
                "release_id": release_id,
                "manifest_hash": "a" * 64,
                "published_at": "2026-09-20T00:00:00Z",
                "pattern_count": 0,
            }
        )
    )
    (root / "search-index.json").write_text(json.dumps({"release_id": release_id, "items": []}))
    (root / "search").mkdir()
    (root / "search/index.html").write_text(release_id)


class PagesProtocol:
    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact
        self.deployments: list[dict[str, object]] = []
        self.active = "prior-deployment"
        self.rollback_calls = 0

        protocol = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def do_GET(self) -> None:
                path = urlsplit(self.path).path
                if path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "https://example.invalid/")
                    self.end_headers()
                    return
                prefix = "/client/v4/accounts/" + "a" * 32 + "/pages/projects/project"
                if path == prefix + "/deployments":
                    body = {"success": True, "result": protocol.deployments}
                elif path == prefix:
                    body = {
                        "success": True,
                        "result": {"canonical_deployment": {"id": protocol.active}},
                    }
                elif path.startswith(prefix + "/deployments/"):
                    deployment_id = path.rsplit("/", 1)[-1]
                    row = next(
                        (row for row in protocol.deployments if row["id"] == deployment_id), None
                    )
                    if row is None:
                        self.send_error(404)
                        return
                    body = {"success": True, "result": row}
                else:
                    relative = path.lstrip("/") or "index.html"
                    if relative.endswith("/"):
                        relative += "index.html"
                    file = protocol.artifact / relative
                    if not file.is_file():
                        self.send_error(404)
                        return
                    content = file.read_bytes()
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(content)
                    return
                content = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(content)

            def do_POST(self) -> None:
                if not self.path.endswith("/rollback"):
                    self.send_error(404)
                    return
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                protocol.rollback_calls += 1
                protocol.active = self.path.split("/")[-2]
                body = json.dumps({"success": True, "result": {"id": protocol.active}}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> PagesProtocol:
        self.thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"


def test_pages_upload_receipt_smoke_rollback_and_uncertain_retry(tmp_path: Path) -> None:
    release_id = str(uuid4())
    artifact = tmp_path / "site"
    _artifact(artifact, release_id)
    digest = artifact_hash(artifact)
    commit = "a" * 40
    operation = "local-protocol-1"
    marker = f"scam-radar:{release_id}:{digest[:16]}:{operation}"

    with PagesProtocol(artifact) as server:
        calls = 0

        def upload(argv: list[str], _environment: dict[str, str]) -> None:
            nonlocal calls
            calls += 1
            assert "--commit-message" in argv
            assert argv[argv.index("--commit-message") + 1] == marker
            server.deployments.append(
                {
                    "id": "deployment-new",
                    "environment": "production",
                    "deployment_trigger": {
                        "metadata": {
                            "commit_message": marker,
                            "commit_hash": commit,
                            "branch": "main",
                        }
                    },
                    "latest_stage": {"status": "success"},
                    "url": server.origin,
                }
            )

        pages = CloudflarePages(
            account_id="a" * 32,
            project_name="project",
            token="synthetic-local-token",
            api_origin=server.origin,
            local_test=True,
            runner=upload,
            sleep=lambda _seconds: None,
        )
        receipt = pages.upload(
            artifact=artifact,
            release_id=release_id,
            branch="main",
            environment="production",
            commit_sha=commit,
            operation_id=operation,
        )
        assert receipt["artifact_hash"] == digest
        assert receipt["deployment_id"] == "deployment-new"
        assert calls == 1
        assert (
            pages.inspect(
                release_id=release_id,
                digest=digest,
                branch="main",
                environment="production",
                commit_sha=commit,
                operation_id=operation,
            )
            == receipt
        )
        pages.smoke(server.origin, json.loads((artifact / "release.json").read_text()))
        with pytest.raises(HTTPError) as redirect:
            pages._get_public_bytes(server.origin + "/redirect")
        assert redirect.value.code == 302

        server.active = "deployment-new"
        rollback = pages.rollback(
            target_deployment_id="deployment-new",
            target_release_id=release_id,
            artifact_hash_value=digest,
            expected_active_deployment_id="deployment-new",
        )
        assert rollback["release_id"] == release_id
        assert server.rollback_calls == 1
        with pytest.raises(RuntimeError, match="pages_active_deployment_changed"):
            pages.rollback(
                target_deployment_id="deployment-new",
                target_release_id=release_id,
                artifact_hash_value=digest,
                expected_active_deployment_id="another-deployment",
            )
        assert server.rollback_calls == 1

        pages.runner = lambda _argv, _env: None
        prior = server.deployments.pop()
        with pytest.raises(RuntimeError, match="pages_upload_receipt_uncertain"):
            pages.upload(
                artifact=artifact,
                release_id=release_id,
                branch="main",
                environment="production",
                commit_sha=commit,
                operation_id="different-operation",
            )
        server.deployments.append(prior)
        with pytest.raises(RuntimeError, match="pages_prior_upload_requires_reconciliation"):
            pages.upload(
                artifact=artifact,
                release_id=release_id,
                branch="main",
                environment="production",
                commit_sha=commit,
                operation_id="another-attempt",
            )
        assert calls == 1
