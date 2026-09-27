"""Narrow release RPC entry for local tests and separately activated deployment."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worker/src"))

from scam_radar.storage.public_export import map_database_release

from scripts.deploy_public_release import PostgrestReleaseRpc, artifact_hash

LIVE_CONFIRMATION = "DEPLOY APPROVED IMMUTABLE RELEASE"


def required(value: str | None, code: str) -> str:
    if not value:
        raise ValueError(code)
    return value


def validate_hash(value: str | None, code: str) -> str:
    value = required(value, code)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(code)
    return value


def validate_release_id(value: str | None) -> str:
    return str(UUID(required(value, "release_id_required")))


def artifact_digest(artifact: Path | None, declared: str | None) -> str:
    if artifact is None:
        return validate_hash(declared, "artifact_hash_invalid")
    measured = artifact_hash(artifact.resolve())
    if declared is not None and declared != measured:
        raise ValueError("artifact_hash_mismatch")
    return measured


def deployment_id(value: str | None, receipt_path: Path | None) -> str:
    if receipt_path is not None:
        path = receipt_path.resolve()
        if not path.is_relative_to(ROOT / "work"):
            raise ValueError("work_receipt_required")
        receipt = json.loads(path.read_text())
        if not isinstance(receipt, dict) or not isinstance(
            receipt.get("deployment_id"), str
        ):
            raise ValueError("deployment_receipt_invalid")
        if value is not None and value != receipt["deployment_id"]:
            raise ValueError("deployment_receipt_mismatch")
        value = receipt["deployment_id"]
    value = required(value, "deployment_id_required")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value):
        raise ValueError("deployment_id_invalid")
    return value


def run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("export", "mark", "note", "record", "fail", "rollback", "withdraw"),
    )
    parser.add_argument("--mode", choices=("local", "live"), default="local")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--artifact-hash")
    parser.add_argument("--commit-sha")
    parser.add_argument("--deployment-id")
    parser.add_argument("--failed-deployment-id")
    parser.add_argument("--receipt-file", type=Path)
    parser.add_argument("--expected-active-release-id")
    parser.add_argument("--expected-active-deployment-id")
    parser.add_argument("--reason-code")
    args = parser.parse_args()

    if args.mode == "live" and (
        os.getenv("SCAM_RADAR_DEPLOY_ENABLED") != "true"
        or os.getenv("SCAM_RADAR_LIVE_ACTIVATION_APPROVED") != "true"
        or os.getenv("SCAM_RADAR_DEPLOY_CONFIRMATION") != LIVE_CONFIRMATION
    ):
        raise ValueError("external_deployment_activation_required")
    release_id = validate_release_id(args.release_id)
    token = required(
        os.getenv("SCAM_RADAR_SUPABASE_SERVICE_KEY"), "service_credential_required"
    )
    rpc = PostgrestReleaseRpc(
        args.api_url,
        token,
        external_enabled=args.mode == "live",
    )
    if args.action == "export":
        if args.destination is None:
            raise ValueError("export_destination_required")
        destination = args.destination.resolve()
        if destination.exists() or not destination.is_relative_to(ROOT / "work"):
            raise ValueError("new_work_export_destination_required")
        raw = rpc.export(release_id)
        if not isinstance(raw, dict):
            raise ValueError("release_export_invalid")
        mapped = map_database_release(raw, release_id)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(mapped, ensure_ascii=False, indent=2) + "\n")
    elif args.action == "mark":
        commit_sha = required(args.commit_sha, "commit_sha_required")
        if not re.fullmatch(r"[0-9a-f]{7,64}", commit_sha):
            raise ValueError("commit_sha_invalid")
        rpc.mark_deploying(
            release_id,
            artifact_digest(args.artifact, args.artifact_hash),
            commit_sha,
        )
    elif args.action in ("note", "record"):
        receipt_id = deployment_id(args.deployment_id, args.receipt_file)
        digest = artifact_digest(args.artifact, args.artifact_hash)
        if args.action == "note":
            rpc.note_uploaded(release_id, receipt_id, digest)
        else:
            rpc.record_deployed(release_id, receipt_id, digest)
    elif args.action == "fail":
        reason = required(args.reason_code, "reason_code_required")
        if not re.fullmatch(r"[a-z0-9_]{1,100}", reason):
            raise ValueError("reason_code_invalid")
        rpc.record_failure(release_id, reason)
    elif args.action == "rollback":
        reason = required(args.reason_code, "reason_code_required")
        if not re.fullmatch(r"[a-z0-9_]{1,100}", reason):
            raise ValueError("reason_code_invalid")
        rpc.record_rollback(
            target_release_id=release_id,
            expected_active_release_id=validate_release_id(
                args.expected_active_release_id
            ),
            expected_active_deployment_id=required(
                args.expected_active_deployment_id,
                "expected_active_deployment_id_required",
            ),
            rollback_deployment_id=deployment_id(args.deployment_id, args.receipt_file),
            digest=artifact_digest(args.artifact, args.artifact_hash),
            reason_code=reason,
        )
    else:
        reason = required(args.reason_code, "reason_code_required")
        if not re.fullmatch(r"[a-z0-9_]{1,100}", reason):
            raise ValueError("reason_code_invalid")
        rpc.record_unrecorded_upload_rollback(
            failed_release_id=release_id,
            failed_deployment_id=deployment_id(args.failed_deployment_id, None),
            expected_active_release_id=validate_release_id(
                args.expected_active_release_id
            ),
            expected_active_deployment_id=deployment_id(
                args.expected_active_deployment_id, None
            ),
            restored_deployment_id=deployment_id(args.deployment_id, args.receipt_file),
            restored_artifact_hash=artifact_digest(args.artifact, args.artifact_hash),
            reason_code=reason,
        )
    print(f"release_rpc_{args.action}_ok release_id={release_id}")
    return 0


def main() -> int:
    try:
        return run()
    except HTTPError as error:
        error.close()
        print(f"release_rpc_http_{error.code}", file=sys.stderr)
    except (URLError, TimeoutError, OSError):
        print("release_rpc_transport_error", file=sys.stderr)
    except (ValueError, RuntimeError) as error:
        print(f"release_rpc_rejected:{error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
