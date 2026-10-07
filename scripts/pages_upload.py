"""Cloudflare Pages Direct Upload adapter; live use requires final activation.

The adapter can be exercised with an injected localhost API and uploader. The
default command targets Cloudflare only after the exact workflow gates pass.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.deploy_public_release import artifact_hash

WRANGLER_VERSION = "4.130.0"  # Same reviewed version as the existing preview workflows.
DEPLOY_CONFIRMATION = "DEPLOY APPROVED IMMUTABLE RELEASE"
ROLLBACK_CONFIRMATION = "ROLLBACK APPROVED VERIFIED ARTIFACT"


def _runner(argv: list[str], environment: dict[str, str]) -> None:
    result = subprocess.run(
        argv,
        env=environment,
        cwd=ROOT,
        capture_output=True,
        check=False,
        timeout=180,
    )
    if result.returncode:
        # Wrangler output can include URLs or environment detail; never echo it.
        raise RuntimeError("pages_upload_command_failed")


class CloudflarePages:
    def __init__(
        self,
        *,
        account_id: str,
        project_name: str,
        token: str,
        api_origin: str = "https://api.cloudflare.com",
        local_test: bool = False,
        canonical_origin: str | None = None,
        runner: Callable[[list[str], dict[str, str]], None] = _runner,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", account_id):
            raise ValueError("cloudflare_account_id_invalid")
        if not re.fullmatch(r"[a-z0-9-]{1,58}", project_name):
            raise ValueError("cloudflare_project_invalid")
        parts = urlsplit(api_origin)
        if local_test:
            if (
                parts.scheme != "http"
                or parts.hostname != "127.0.0.1"
                or not parts.port
            ):
                raise ValueError("local_pages_api_must_be_loopback")
        elif api_origin != "https://api.cloudflare.com":
            raise ValueError("official_pages_api_required")
        self.account_id = account_id
        self.project_name = project_name
        self.token = token
        self.api_origin = api_origin.rstrip("/")
        self.local_test = local_test
        self.canonical_origin = canonical_origin
        if canonical_origin is not None:
            parts = urlsplit(canonical_origin)
            if (
                local_test
                or parts.scheme != "https"
                or not parts.hostname
                or parts.username
                or parts.password
                or parts.port
                or parts.path not in ("", "/")
                or parts.query
                or parts.fragment
            ):
                raise ValueError("canonical_site_origin_invalid")
        self.runner = runner
        self.sleep = sleep
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _api(
        self, method: str, path: str, payload: dict[str, str] | None = None
    ) -> Any:
        if not self.token:
            raise ValueError("cloudflare_token_required")
        request = Request(
            self.api_origin + path,
            data=None if payload is None else json.dumps(payload).encode(),
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        with self.opener.open(request, timeout=20) as response:
            if response.status not in (200, 201):
                raise RuntimeError("pages_api_status_invalid")
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise RuntimeError("pages_api_response_too_large")
        result = json.loads(data)
        if not isinstance(result, dict) or result.get("success") is not True:
            raise RuntimeError("pages_api_rejected")
        return result.get("result")

    def _project_path(self) -> str:
        return f"/client/v4/accounts/{self.account_id}/pages/projects/" + quote(
            self.project_name, safe=""
        )

    def deployments(self, environment: str) -> list[dict[str, Any]]:
        if environment not in ("preview", "production"):
            raise ValueError("pages_environment_invalid")
        rows: list[dict[str, Any]] = []
        for page in range(1, 11):
            query = urlencode({"env": environment, "page": page, "per_page": 100})
            result = self._api("GET", self._project_path() + "/deployments?" + query)
            if not isinstance(result, list) or any(
                not isinstance(row, dict) for row in result
            ):
                raise TypeError("pages_deployment_list_invalid")
            rows.extend(result)
            if len(result) < 100:
                return rows
        raise RuntimeError("pages_deployment_list_truncated")

    def inspect(
        self,
        *,
        release_id: str,
        digest: str,
        branch: str,
        environment: str,
        commit_sha: str,
        operation_id: str,
    ) -> dict[str, str]:
        release_id = str(UUID(release_id))
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("pages_artifact_hash_invalid")
        if not re.fullmatch(r"[a-z0-9][a-z0-9/_-]{0,80}", branch):
            raise ValueError("pages_branch_invalid")
        if not re.fullmatch(r"[0-9a-f]{7,64}", commit_sha):
            raise ValueError("pages_commit_invalid")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", operation_id):
            raise ValueError("pages_operation_id_invalid")
        marker = f"scam-radar:{release_id}:{digest[:16]}:{operation_id}"
        matching = []
        for row in self.deployments(environment):
            metadata = (row.get("deployment_trigger") or {}).get("metadata") or {}
            if (
                metadata.get("commit_message") == marker
                and metadata.get("commit_hash") == commit_sha
                and metadata.get("branch") == branch
                and row.get("environment") == environment
            ):
                matching.append(row)
        if len(matching) != 1:
            raise RuntimeError("pages_upload_receipt_missing_or_ambiguous")
        row = matching[0]
        if (
            row.get("is_skipped")
            or (row.get("latest_stage") or {}).get("status") != "success"
        ):
            raise RuntimeError("pages_upload_not_successful")
        deployment_id = row.get("id")
        url = row.get("url")
        if not isinstance(deployment_id, str) or not isinstance(url, str):
            raise TypeError("pages_upload_receipt_invalid")
        self._validate_site_origin(url)
        return {
            "deployment_id": deployment_id,
            "deployment_url": url,
            "release_id": release_id,
            "artifact_hash": digest,
            "environment": environment,
            "branch": branch,
            "operation_id": operation_id,
        }

    def active_deployment_id(self) -> str:
        result = self._api("GET", self._project_path())
        if not isinstance(result, dict):
            raise TypeError("pages_project_invalid")
        canonical = result.get("canonical_deployment")
        if not isinstance(canonical, dict) or not isinstance(canonical.get("id"), str):
            raise TypeError("pages_current_deployment_unknown")
        return canonical["id"]

    def upload(
        self,
        *,
        artifact: Path,
        release_id: str,
        branch: str,
        environment: str,
        commit_sha: str,
        operation_id: str,
    ) -> dict[str, str]:
        release_id = str(UUID(release_id))
        digest = artifact_hash(artifact)
        metadata = json.loads((artifact / "release.json").read_text())
        if metadata.get("release_id") != release_id:
            raise ValueError("pages_artifact_release_mismatch")
        if not re.fullmatch(r"[a-z0-9][a-z0-9/_-]{0,80}", branch):
            raise ValueError("pages_branch_invalid")
        if not re.fullmatch(r"[0-9a-f]{7,64}", commit_sha):
            raise ValueError("pages_commit_invalid")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", operation_id):
            raise ValueError("pages_operation_id_invalid")
        if environment not in ("preview", "production"):
            raise ValueError("pages_environment_invalid")
        marker = f"scam-radar:{release_id}:{digest[:16]}:{operation_id}"
        previous = self.deployments(environment)
        prefix = f"scam-radar:{release_id}:{digest[:16]}:"
        for row in previous:
            metadata = (row.get("deployment_trigger") or {}).get("metadata") or {}
            if (
                isinstance(metadata.get("commit_message"), str)
                and metadata["commit_message"].startswith(prefix)
                and metadata.get("branch") == branch
            ):
                # A prior invocation may already have published this artifact.
                # Its receipt must be reconciled; a retry must not upload again.
                raise RuntimeError("pages_prior_upload_requires_reconciliation")
        before = {row.get("id") for row in previous}
        environment_values = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "TMPDIR")
            if key in os.environ
        }
        environment_values.update(
            CLOUDFLARE_API_TOKEN=self.token,
            CLOUDFLARE_ACCOUNT_ID=self.account_id,
            CI="true",
            WRANGLER_SEND_METRICS="false",
        )
        self.runner(
            [
                "npx",
                "--yes",
                f"wrangler@{WRANGLER_VERSION}",
                "pages",
                "deploy",
                str(artifact.resolve()),
                "--project-name",
                self.project_name,
                "--branch",
                branch,
                "--commit-hash",
                commit_sha,
                "--commit-message",
                marker,
            ],
            environment_values,
        )
        for attempt in range(6):
            matching = []
            for row in self.deployments(environment):
                trigger = row.get("deployment_trigger") or {}
                metadata = trigger.get("metadata") or {}
                if (
                    row.get("id") not in before
                    and metadata.get("commit_message") == marker
                    and metadata.get("commit_hash") == commit_sha
                    and metadata.get("branch") == branch
                    and row.get("environment") == environment
                ):
                    matching.append(row)
            if len(matching) > 1:
                raise RuntimeError("pages_upload_receipt_ambiguous")
            if matching:
                row = matching[0]
                if (
                    row.get("is_skipped")
                    or row.get("latest_stage", {}).get("status") == "failure"
                ):
                    raise RuntimeError("pages_upload_failed")
                if row.get("latest_stage", {}).get("status") == "success":
                    deployment_id = row.get("id")
                    url = row.get("url")
                    if not isinstance(deployment_id, str) or not isinstance(url, str):
                        raise RuntimeError("pages_upload_receipt_invalid")
                    self._validate_site_origin(url)
                    return {
                        "deployment_id": deployment_id,
                        "deployment_url": url,
                        "release_id": release_id,
                        "artifact_hash": digest,
                        "environment": environment,
                        "branch": branch,
                        "operation_id": operation_id,
                    }
            if attempt < 5:
                self.sleep(2)
        # Upload may have succeeded. Never blindly retry it.
        raise RuntimeError("pages_upload_receipt_uncertain")

    def rollback(
        self,
        *,
        target_deployment_id: str,
        target_release_id: str,
        artifact_hash_value: str,
        expected_active_deployment_id: str,
    ) -> dict[str, str]:
        target_release_id = str(UUID(target_release_id))
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", target_deployment_id):
            raise ValueError("pages_target_deployment_id_invalid")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", expected_active_deployment_id):
            raise ValueError("pages_expected_deployment_id_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", artifact_hash_value):
            raise ValueError("pages_artifact_hash_invalid")
        if self.active_deployment_id() != expected_active_deployment_id:
            raise RuntimeError("pages_active_deployment_changed")
        target = self._api(
            "GET",
            self._project_path()
            + "/deployments/"
            + quote(target_deployment_id, safe=""),
        )
        if not isinstance(target, dict) or target.get("environment") != "production":
            raise RuntimeError("pages_rollback_target_not_production")
        marker = (target.get("deployment_trigger") or {}).get("metadata") or {}
        marker = marker.get("commit_message", "")
        if (
            not isinstance(marker, str)
            or not marker.startswith(
                f"scam-radar:{target_release_id}:{artifact_hash_value[:16]}:"
            )
            or (target.get("latest_stage") or {}).get("status") != "success"
        ):
            raise RuntimeError("pages_rollback_target_mismatch")
        target_url = target.get("url")
        if not isinstance(target_url, str):
            raise TypeError("pages_rollback_target_url_invalid")
        self._validate_site_origin(target_url)
        result = self._api(
            "POST",
            self._project_path()
            + "/deployments/"
            + quote(target_deployment_id, safe="")
            + "/rollback",
            {},
        )
        if not isinstance(result, dict) or not isinstance(result.get("id"), str):
            raise TypeError("pages_rollback_receipt_invalid")
        for attempt in range(6):
            current = self.active_deployment_id()
            if current in (target_deployment_id, result["id"]):
                return {
                    "deployment_id": current,
                    "deployment_url": target_url,
                    "release_id": target_release_id,
                    "artifact_hash": artifact_hash_value,
                    "environment": "production",
                }
            if attempt < 5:
                self.sleep(2)
        # Rollback may have succeeded. Never issue it a second time blindly.
        raise RuntimeError("pages_rollback_receipt_uncertain")

    def _validate_site_origin(self, origin: str) -> None:
        if origin == self.canonical_origin:
            return
        parts = urlsplit(origin)
        if self.local_test:
            if (
                parts.scheme != "http"
                or parts.hostname != "127.0.0.1"
                or not parts.port
            ):
                raise ValueError("local_pages_site_must_be_loopback")
        elif parts.scheme != "https" or not (parts.hostname or "").endswith(
            ".pages.dev"
        ):
            raise ValueError("pages_deployment_url_invalid")
        if (
            parts.username
            or parts.password
            or parts.path not in ("", "/")
            or parts.query
            or parts.fragment
        ):
            raise ValueError("pages_site_origin_invalid")

    def smoke(self, origin: str, expected_release: dict[str, Any]) -> None:
        self._validate_site_origin(origin)
        origin = origin.rstrip("/")
        release = self._get_public_json(origin + "/release.json")
        search = self._get_public_json(origin + "/search-index.json")
        expected_count = expected_release.get("pattern_count")
        if expected_count is None and isinstance(
            expected_release.get("patterns"), list
        ):
            expected_count = len(expected_release["patterns"])
        for field in ("release_id", "manifest_hash", "published_at"):
            if release.get(field) != expected_release.get(field):
                raise RuntimeError("pages_smoke_release_mismatch")
        if release.get("pattern_count") != expected_count or search.get(
            "release_id"
        ) != release.get("release_id"):
            raise RuntimeError("pages_smoke_index_mismatch")
        for path in ("/", "/search/"):
            self._get_public_bytes(origin + path)
        items = search.get("items")
        if not isinstance(items, list) or len(items) != expected_count:
            raise RuntimeError("pages_smoke_search_items_mismatch")
        if items:
            slug = items[0].get("slug")
            if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9-]+", slug):
                raise RuntimeError("pages_smoke_slug_invalid")
            self._get_public_bytes(origin + "/scam/" + slug + "/")

    def _get_public_bytes(self, url: str) -> bytes:
        with self.opener.open(Request(url, method="GET"), timeout=15) as response:
            if response.status != 200:
                raise RuntimeError("pages_smoke_http_status_invalid")
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise RuntimeError("pages_smoke_response_too_large")
            return body

    def _get_public_json(self, url: str) -> dict[str, Any]:
        result = json.loads(self._get_public_bytes(url))
        if not isinstance(result, dict):
            raise TypeError("pages_smoke_json_invalid")
        return result


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object) -> None:
        return None


def _live_gate(action: str) -> None:
    if (
        os.getenv("SCAM_RADAR_DEPLOY_ENABLED") != "true"
        or os.getenv("SCAM_RADAR_LIVE_ACTIVATION_APPROVED") != "true"
        or os.getenv("SCAM_RADAR_DEPLOY_CONFIRMATION") != DEPLOY_CONFIRMATION
    ):
        raise ValueError("external_pages_activation_required")
    if (
        action == "rollback"
        and os.getenv("SCAM_RADAR_ROLLBACK_CONFIRMATION") != ROLLBACK_CONFIRMATION
    ):
        raise ValueError("explicit_rollback_confirmation_required")


def _write_receipt(path: Path, receipt: dict[str, str]) -> None:
    destination = path.resolve()
    if not destination.is_relative_to(ROOT / "work") or destination.exists():
        raise ValueError("new_work_receipt_required")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")


def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("upload", "inspect", "smoke", "rollback"))
    parser.add_argument("--mode", choices=("live",), required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--release-path", type=Path)
    parser.add_argument("--release-id")
    parser.add_argument("--branch")
    parser.add_argument("--environment", choices=("preview", "production"))
    parser.add_argument("--commit-sha")
    parser.add_argument("--operation-id")
    parser.add_argument("--receipt-file", type=Path)
    parser.add_argument("--output-receipt", type=Path)
    parser.add_argument("--canonical-origin")
    parser.add_argument("--target-deployment-id")
    parser.add_argument("--expected-active-deployment-id")
    parser.add_argument("--artifact-hash")
    args = parser.parse_args()
    _live_gate(args.action)
    from scripts.cloudflare_account_guard import require_dedicated_account

    require_dedicated_account(args.account_id)
    token = os.getenv("CLOUDFLARE_API_TOKEN", "")
    canonical_origin = args.canonical_origin
    if canonical_origin is not None and canonical_origin != os.getenv(
        "SCAM_RADAR_CANONICAL_ORIGIN"
    ):
        raise ValueError("approved_canonical_origin_required")
    pages = CloudflarePages(
        account_id=args.account_id,
        project_name=args.project_name,
        token=token,
        canonical_origin=canonical_origin,
    )
    if args.action == "upload":
        if not all(
            (
                args.artifact,
                args.release_id,
                args.branch,
                args.environment,
                args.commit_sha,
                args.operation_id,
                args.output_receipt,
            )
        ):
            raise ValueError("pages_upload_arguments_required")
        receipt = pages.upload(
            artifact=args.artifact,
            release_id=args.release_id,
            branch=args.branch,
            environment=args.environment,
            commit_sha=args.commit_sha,
            operation_id=args.operation_id,
        )
        _write_receipt(args.output_receipt, receipt)
    elif args.action == "inspect":
        if not all(
            (
                args.artifact,
                args.release_id,
                args.branch,
                args.environment,
                args.commit_sha,
                args.operation_id,
                args.output_receipt,
            )
        ):
            raise ValueError("pages_inspect_arguments_required")
        receipt = pages.inspect(
            release_id=args.release_id,
            digest=artifact_hash(args.artifact),
            branch=args.branch,
            environment=args.environment,
            commit_sha=args.commit_sha,
            operation_id=args.operation_id,
        )
        _write_receipt(args.output_receipt, receipt)
    elif args.action == "smoke":
        if args.release_path is None or args.receipt_file is None:
            raise ValueError("pages_smoke_inputs_required")
        expected = json.loads(args.release_path.read_text())
        receipt = json.loads(args.receipt_file.read_text())
        origin = args.canonical_origin or receipt.get("deployment_url")
        if not isinstance(origin, str) or not isinstance(expected, dict):
            raise ValueError("pages_smoke_inputs_invalid")
        pages.smoke(origin, expected)
    else:
        if not all(
            (
                args.target_deployment_id,
                args.release_id,
                args.artifact_hash,
                args.expected_active_deployment_id,
                args.output_receipt,
            )
        ):
            raise ValueError("pages_rollback_arguments_required")
        receipt = pages.rollback(
            target_deployment_id=args.target_deployment_id,
            target_release_id=args.release_id,
            artifact_hash_value=args.artifact_hash,
            expected_active_deployment_id=args.expected_active_deployment_id,
        )
        _write_receipt(args.output_receipt, receipt)
    print(f"pages_{args.action}_ok")
    return 0


def main() -> int:
    try:
        return run()
    except HTTPError as error:
        error.close()
        print(f"pages_http_{error.code}", file=sys.stderr)
    except (URLError, TimeoutError, OSError):
        print("pages_transport_error", file=sys.stderr)
    except (ValueError, TypeError, RuntimeError, KeyError) as error:
        print(f"pages_rejected:{error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
