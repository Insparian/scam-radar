"""Executable self-contained offline release-recovery rehearsal."""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Self
from urllib.error import HTTPError

try:
    from scripts.deploy_public_release import (
        JsonHttp,
        LocalPages,
        ReleaseRpc,
        artifact_hash,
        publish,
        reconcile,
    )
except ModuleNotFoundError:
    from deploy_public_release import (
        JsonHttp,
        LocalPages,
        ReleaseRpc,
        artifact_hash,
        publish,
        reconcile,
    )


class RehearsalServer:
    def __init__(self, release_id: str, artifact_hash_value: str) -> None:
        self.release_id, self.artifact_hash = release_id, artifact_hash_value
        self.database_current_release = "original-release"
        self.pages_current_release = "original-release"
        self.original_deployment = "original-artifact"
        self.record_failures = 1
        self.database_pending_receipt: tuple[str, str, str] | None = None
        self.deployments: dict[str, tuple[str, str]] = {
            self.original_deployment: (self.pages_current_release, "original-hash")
        }
        self.marked: list[str] = []
        server_state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def payload(self) -> dict[str, str]:
                size = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(size) or b"{}")

            def reply(self, status: int, body: dict[str, str]) -> None:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_GET(self) -> None:
                deployment_id = self.path.removeprefix(
                    "/pages/deployments/"
                ).removesuffix("/release.json")
                deployed = server_state.deployments.get(deployment_id)
                self.reply(
                    200 if deployed else 404,
                    {"release_id": deployed[0]} if deployed else {"error": "missing"},
                )

            def do_POST(self) -> None:
                body = self.payload()
                if self.path.endswith("mark_release_deploying"):
                    if body["release_id"] == "older-release":
                        self.reply(
                            409, {"error": "older_release_cannot_overwrite_newer"}
                        )
                        return
                    server_state.marked.append(body["release_id"])
                    self.reply(200, {})
                    return
                if self.path.endswith("record_deployed_release"):
                    if server_state.database_pending_receipt != (
                        body["release_id"],
                        body["deployment_id"],
                        body["artifact_hash"],
                    ):
                        self.reply(409, {"error": "missing_upload_receipt"})
                        return
                    if server_state.record_failures:
                        server_state.record_failures -= 1
                        self.reply(500, {"error": "record_failed"})
                        return
                    server_state.database_current_release = body["release_id"]
                    self.reply(200, {})
                    return
                if self.path.endswith("note_release_uploaded"):
                    server_state.database_pending_receipt = (
                        body["release_id"],
                        body["deployment_id"],
                        body["artifact_hash"],
                    )
                    self.reply(200, {})
                    return
                if self.path == "/pages/deployments":
                    deployment_id = f"deploy-{len(server_state.deployments)}"
                    server_state.deployments[deployment_id] = (
                        body["release_id"],
                        body["artifact_hash"],
                    )
                    if body["branch"] == "production":
                        server_state.pages_current_release = body["release_id"]
                    self.reply(201, {"deployment_id": deployment_id})
                    return
                if self.path == "/pages/rollback":
                    original = server_state.deployments.get(body["deployment_id"])
                    if not original or original[1] != body["artifact_hash"]:
                        self.reply(409, {"error": "original_artifact_mismatch"})
                        return
                    server_state.pages_current_release = original[0]
                    self.reply(200, {"deployment_id": body["deployment_id"]})
                    return
                self.reply(404, {"error": "missing"})

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.http.server_port}"

    def __enter__(self) -> Self:
        self.thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--commit-sha", default="a" * 40)
    args = parser.parse_args()
    digest = artifact_hash(args.artifact)
    with RehearsalServer(args.release_id, digest) as server:
        rpc, pages = (
            ReleaseRpc(JsonHttp(server.origin)),
            LocalPages(JsonHttp(server.origin)),
        )
        try:
            artifact_hash(args.artifact / "missing-build-output")
        except (FileNotFoundError, RuntimeError):
            pass
        else:
            raise RuntimeError("simulated_build_failure_was_accepted")
        if server.pages_current_release != "original-release":
            raise RuntimeError("build_failure_replaced_current_release")
        result = publish(
            rpc=rpc,
            pages=pages,
            artifact=args.artifact,
            release_id=args.release_id,
            commit_sha=args.commit_sha,
        )
        if (
            not result.reconciliation_required
            or server.database_current_release != "original-release"
            or server.pages_current_release != args.release_id
            or server.database_pending_receipt is None
        ):
            raise RuntimeError("record_failure_did_not_preserve_current_release")
        reconcile(
            rpc=rpc,
            pages=pages,
            release_id=args.release_id,
            deployment_id=result.production_deployment_id,
            digest=digest,
        )
        if server.database_current_release != args.release_id:
            raise RuntimeError("reconciliation_failed")
        restored = pages.rollback(server.original_deployment, "original-hash")
        if (
            restored != server.original_deployment
            or server.pages_current_release != "original-release"
        ):
            raise RuntimeError("original_artifact_rollback_failed")
        try:
            rpc.mark_deploying("older-release", digest, args.commit_sha)
        except HTTPError:
            print("older release rejected by local RPC")
        else:
            raise RuntimeError("older_release_protection_missing")
    print(
        "offline deploy rehearsal passed: build failure/current preservation, receipt reconciliation, original artifact rollback, older release protection"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
