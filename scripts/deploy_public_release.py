"""Guarded release publication protocol.

This command is deliberately limited to loopback HTTP.  It exercises the same
ordering required for Pages: freeze the release, validate one artifact, upload
that artifact to preview and production, then record the receipt.  A real Pages
upload remains an activation-only workflow action; this script is its offline
protocol rehearsal and never accepts a remote destination.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker" / "src"))
from scam_radar.collectors.http import BoundedHttpTransport, NoRedirect

CONFIRMATION = "REHEARSE IMMUTABLE RELEASE"


def require_loopback_origin(origin: str) -> None:
    transport = BoundedHttpTransport(allowed_origins={origin}, min_interval=0)
    transport.validate_url(origin)


def artifact_hash(artifact: Path) -> str:
    try:
        from scripts.check_pages_artifact import validate_pages_artifact
    except ModuleNotFoundError:
        from check_pages_artifact import validate_pages_artifact

    release = json.loads((artifact / "release.json").read_text(encoding="utf-8"))
    release_id = release.get("release_id")
    if not isinstance(release_id, str):
        raise TypeError("artifact_release_id_missing")
    return validate_pages_artifact(artifact, release_id).artifact_hash


class JsonHttp:
    def __init__(self, origin: str) -> None:
        require_loopback_origin(origin)
        self.origin = origin.rstrip("/")
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(self, method: str, path: str, payload: dict[str, str]) -> dict[str, str]:
        request = Request(
            self.origin + path,
            data=(
                None
                if method == "GET"
                else json.dumps(payload, separators=(",", ":")).encode()
            ),
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with self.opener.open(request, timeout=15) as response:
            data = response.read(100_001)
            if len(data) > 100_000:
                raise RuntimeError("local_protocol_response_too_large")
            if response.status not in (200, 201):
                raise RuntimeError("local_protocol_http_failure")
        result = json.loads(data)
        if not isinstance(result, dict) or any(
            not isinstance(v, str) for v in result.values()
        ):
            raise RuntimeError("local_protocol_invalid_response")
        return result


class ReleaseRpc:
    def __init__(self, client: JsonHttp) -> None:
        self.client = client

    def mark_deploying(self, release_id: str, digest: str, commit_sha: str) -> None:
        self.client.call(
            "POST",
            "/rpc/mark_release_deploying",
            {
                "release_id": release_id,
                "artifact_hash": digest,
                "commit_sha": commit_sha,
            },
        )

    def record_deployed(self, release_id: str, deployment_id: str, digest: str) -> None:
        self.client.call(
            "POST",
            "/rpc/record_deployed_release",
            {
                "release_id": release_id,
                "deployment_id": deployment_id,
                "artifact_hash": digest,
            },
        )

    def note_uploaded(self, release_id: str, deployment_id: str, digest: str) -> None:
        self.client.call(
            "POST",
            "/rpc/note_release_uploaded",
            {
                "release_id": release_id,
                "deployment_id": deployment_id,
                "artifact_hash": digest,
            },
        )


class ReleaseStateGateway(Protocol):
    def mark_deploying(self, release_id: str, digest: str, commit_sha: str) -> None: ...

    def note_uploaded(
        self, release_id: str, deployment_id: str, digest: str
    ) -> None: ...

    def record_deployed(
        self, release_id: str, deployment_id: str, digest: str
    ) -> None: ...


class PostgrestReleaseRpc:
    """Exact release RPCs with a separate, explicit live destination gate."""

    def __init__(
        self,
        origin: str,
        service_token: str,
        *,
        external_enabled: bool = False,
    ) -> None:
        if external_enabled:
            parts = urlsplit(origin)
            if (
                parts.scheme != "https"
                or not re.fullmatch(r"[a-z0-9-]+\.supabase\.co", parts.hostname or "")
                or parts.path not in ("", "/")
                or parts.query
                or parts.fragment
                or parts.username
                or parts.password
            ):
                raise ValueError("approved_supabase_origin_required")
        else:
            require_loopback_origin(origin)
        if not service_token:
            raise ValueError("local_service_token_required")
        self.origin = origin.rstrip("/")
        self.token = service_token
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def _call(self, function: str, payload: dict[str, object]) -> object | None:
        request = Request(
            self.origin + f"/rest/v1/rpc/{function}",
            data=json.dumps(payload, separators=(",", ":")).encode(),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "apikey": self.token,
                "Authorization": f"Bearer {self.token}",
            },
        )
        with self.opener.open(request, timeout=15) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError("local_postgrest_rpc_status_invalid")
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise RuntimeError("local_postgrest_rpc_response_too_large")
            return json.loads(data) if data else None

    def export(self, release_id: str) -> object:
        return self._call("export_public_release", {"p_release_id": release_id})

    def mark_deploying(self, release_id: str, digest: str, commit_sha: str) -> None:
        self._call(
            "mark_release_deploying",
            {
                "p_release_id": release_id,
                "p_artifact_hash": digest,
                "p_commit_sha": commit_sha,
            },
        )

    def note_uploaded(self, release_id: str, deployment_id: str, digest: str) -> None:
        self._call(
            "note_release_uploaded",
            {
                "p_release_id": release_id,
                "p_deployment_id": deployment_id,
                "p_artifact_hash": digest,
            },
        )

    def record_deployed(self, release_id: str, deployment_id: str, digest: str) -> None:
        self._call(
            "record_deployed_release",
            {
                "p_release_id": release_id,
                "p_deployment_id": deployment_id,
                "p_artifact_hash": digest,
            },
        )

    def record_rollback(
        self,
        *,
        target_release_id: str,
        expected_active_release_id: str,
        expected_active_deployment_id: str,
        rollback_deployment_id: str,
        digest: str,
        reason_code: str,
    ) -> None:
        self._call(
            "record_release_rollback",
            {
                "p_target_release_id": target_release_id,
                "p_expected_active_release_id": expected_active_release_id,
                "p_expected_active_deployment_id": expected_active_deployment_id,
                "p_rollback_deployment_id": rollback_deployment_id,
                "p_artifact_hash": digest,
                "p_reason_code": reason_code,
            },
        )

    def record_failure(self, release_id: str, reason_code: str) -> None:
        self._call(
            "record_release_failure",
            {"p_release_id": release_id, "p_redacted_error": reason_code},
        )

    def record_unrecorded_upload_rollback(
        self,
        *,
        failed_release_id: str,
        failed_deployment_id: str,
        expected_active_release_id: str,
        expected_active_deployment_id: str,
        restored_deployment_id: str,
        restored_artifact_hash: str,
        reason_code: str,
    ) -> None:
        self._call(
            "record_unrecorded_upload_rollback",
            {
                "p_failed_release_id": failed_release_id,
                "p_failed_deployment_id": failed_deployment_id,
                "p_expected_active_release_id": expected_active_release_id,
                "p_expected_active_deployment_id": expected_active_deployment_id,
                "p_restored_deployment_id": restored_deployment_id,
                "p_restored_artifact_hash": restored_artifact_hash,
                "p_reason_code": reason_code,
            },
        )


class LocalPostgrestReleaseRpc(PostgrestReleaseRpc):
    """Use actual local Supabase RPCs; never accepts a remote production URL."""

    def __init__(self, origin: str, service_token: str) -> None:
        super().__init__(origin, service_token, external_enabled=False)


class LocalPages:
    def __init__(self, client: JsonHttp) -> None:
        self.client = client

    def upload(self, branch: str, release_id: str, digest: str) -> str:
        result = self.client.call(
            "POST",
            "/pages/deployments",
            {
                "branch": branch,
                "release_id": release_id,
                "artifact_hash": digest,
            },
        )
        deployment_id = result.get("deployment_id")
        if not deployment_id:
            raise RuntimeError("upload_receipt_missing")
        return deployment_id

    def release_id(self, deployment_id: str) -> str:
        result = self.client.call(
            "GET", f"/pages/deployments/{deployment_id}/release.json", {}
        )
        release_id = result.get("release_id")
        if not release_id:
            raise RuntimeError("smoke_release_id_missing")
        return release_id

    def rollback(self, original_deployment_id: str, original_digest: str) -> str:
        result = self.client.call(
            "POST",
            "/pages/rollback",
            {
                "deployment_id": original_deployment_id,
                "artifact_hash": original_digest,
            },
        )
        restored = result.get("deployment_id")
        if not restored:
            raise RuntimeError("rollback_receipt_missing")
        return restored


@dataclass(frozen=True)
class PublicationResult:
    preview_deployment_id: str
    production_deployment_id: str
    reconciliation_required: bool


def publish(
    *,
    rpc: ReleaseStateGateway,
    pages: LocalPages,
    artifact: Path,
    release_id: str,
    commit_sha: str,
) -> PublicationResult:
    digest = artifact_hash(artifact)
    metadata = json.loads((artifact / "release.json").read_text(encoding="utf-8"))
    if metadata.get("release_id") != release_id:
        raise RuntimeError("immutable_release_mismatch")
    rpc.mark_deploying(release_id, digest, commit_sha)
    preview = pages.upload("preview", release_id, digest)
    if pages.release_id(preview) != release_id:
        raise RuntimeError("preview_release_mismatch")
    production = pages.upload("production", release_id, digest)
    if pages.release_id(production) != release_id:
        raise RuntimeError("production_release_mismatch")
    try:
        rpc.note_uploaded(release_id, production, digest)
        rpc.record_deployed(release_id, production, digest)
    except (URLError, TimeoutError, OSError) as error:
        if isinstance(error, HTTPError) and error.code < 500:
            raise
        # A public upload has happened.  The immutable receipt remains sufficient
        # for a later idempotent record_deployed reconciliation attempt.
        return PublicationResult(preview, production, True)
    return PublicationResult(preview, production, False)


def reconcile(
    *,
    rpc: ReleaseStateGateway,
    pages: LocalPages,
    release_id: str,
    deployment_id: str,
    digest: str,
) -> None:
    if pages.release_id(deployment_id) != release_id:
        raise RuntimeError("reconciliation_release_mismatch")
    rpc.note_uploaded(release_id, deployment_id, digest)
    rpc.record_deployed(release_id, deployment_id, digest)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the loopback-only publication protocol."
    )
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--rpc-origin", required=True)
    parser.add_argument("--pages-origin", required=True)
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if (
        os.getenv("SCAM_RADAR_DEPLOY_ENABLED") != "true"
        or args.confirmation != CONFIRMATION
    ):
        raise RuntimeError("deployment_rehearsal_not_authorized")
    result = publish(
        rpc=ReleaseRpc(JsonHttp(args.rpc_origin)),
        pages=LocalPages(JsonHttp(args.pages_origin)),
        artifact=args.artifact.resolve(),
        release_id=args.release_id,
        commit_sha=args.commit_sha,
    )
    print(
        json.dumps(
            {
                "preview_deployment_id": result.preview_deployment_id,
                "production_deployment_id": result.production_deployment_id,
                "reconciliation_required": result.reconciliation_required,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
