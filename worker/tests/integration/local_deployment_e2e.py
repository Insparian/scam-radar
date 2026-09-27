"""Join real local release RPCs to a localhost-only Pages protocol server."""

from __future__ import annotations

import json
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from uuid import UUID, uuid4

from local_pipeline_e2e import LOCAL_API, ROOT, _post_json, local_keys, sql_scalar

from scam_radar.collectors.http import BoundedHttpTransport
from scam_radar.storage.public_export import map_database_release
from scam_radar.storage.rpc import RpcStore

sys.path.insert(0, str(ROOT))
from scripts.deploy_public_release import (
    JsonHttp,
    LocalPages,
    LocalPostgrestReleaseRpc,
    artifact_hash,
    publish,
    reconcile,
)
from scripts.rehearse_deploy import RehearsalServer


class DropFirstRecord:
    def __init__(self, delegate: LocalPostgrestReleaseRpc) -> None:
        self.delegate = delegate
        self.failed = False

    def mark_deploying(self, release_id: str, digest: str, commit_sha: str) -> None:
        self.delegate.mark_deploying(release_id, digest, commit_sha)

    def note_uploaded(self, release_id: str, deployment_id: str, digest: str) -> None:
        self.delegate.note_uploaded(release_id, deployment_id, digest)

    def record_deployed(self, release_id: str, deployment_id: str, digest: str) -> None:
        if not self.failed:
            self.failed = True
            raise URLError("synthetic_record_response_lost")
        self.delegate.record_deployed(release_id, deployment_id, digest)


def create_second_release(
    store: RpcStore, first_release_id: str, keys: dict[str, str]
) -> tuple[str, Path]:
    auth_http = BoundedHttpTransport(allowed_origins={LOCAL_API}, min_interval=0, max_requests=20)
    email = f"local-deploy-admin-{uuid4().hex[:12]}@example.invalid"
    password = secrets.token_urlsafe(24)
    created = _post_json(
        auth_http,
        LOCAL_API + "/auth/v1/admin/users",
        {"email": email, "password": password, "email_confirm": True},
        apikey=keys["service"],
        bearer=keys["service"],
    )
    admin_id = str(UUID(created["id"]))
    sql_scalar(
        "insert into public.admin_users(user_id,role,enabled) values "
        f"('{admin_id}','admin',true) returning user_id"
    )
    session = _post_json(
        auth_http,
        LOCAL_API + "/auth/v1/token?grant_type=password",
        {"email": email, "password": password},
        apikey=keys["anon"],
        bearer=keys["anon"],
    )
    pattern = sql_scalar(
        "select item.pattern_id::text || ':' || pattern.row_version::text "
        "from public.public_release_items as item "
        "join public.scam_patterns as pattern on pattern.id=item.pattern_id "
        f"where item.release_id='{first_release_id}'"
    )
    pattern_id, row_version = pattern.split(":", 1)
    _post_json(
        auth_http,
        LOCAL_API + "/rest/v1/rpc/unpublish_pattern",
        {
            "p_pattern_id": pattern_id,
            "p_expected_row_version": int(row_version),
            "p_reason": "隔离合成演练：生成第二个不可变版本以验证技术回退",
        },
        apikey=keys["anon"],
        bearer=session["access_token"],
    )
    release_id = str(
        UUID(
            store.call(
                "prepare_public_release",
                {"p_expected_previous_release_id": first_release_id},
            )
        )
    )
    mapped = map_database_release(
        store.call("export_public_release", {"p_release_id": release_id}), release_id
    )
    output = ROOT / "work/launch-readiness/deployment-e2e" / release_id
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
    return release_id, output / "site"


def main() -> int:
    if not LOCAL_API.startswith("http://127.0.0.1:"):
        raise RuntimeError("isolated_local_api_required")
    first_release_id = sql_scalar(
        "select id::text from public.public_releases where state='approved' "
        "order by release_no desc limit 1"
    )
    first_artifact = ROOT / "work/launch-readiness/joined-e2e" / first_release_id / "site"
    first_digest = artifact_hash(first_artifact)
    keys = local_keys()
    rpc = LocalPostgrestReleaseRpc(LOCAL_API, keys["service"])
    store = RpcStore(
        transport=BoundedHttpTransport(
            allowed_origins={LOCAL_API}, min_interval=0, max_requests=100
        ),
        base_url=LOCAL_API,
        token=keys["service"],
    )
    initial_export = store.call("export_public_release", {"p_release_id": first_release_id})
    with RehearsalServer(first_release_id, first_digest) as server:
        pages = LocalPages(JsonHttp(server.origin))
        dropped = DropFirstRecord(rpc)
        first = publish(
            rpc=dropped,
            pages=pages,
            artifact=first_artifact,
            release_id=first_release_id,
            commit_sha="a" * 40,
        )
        if not first.reconciliation_required or not dropped.failed:
            raise AssertionError("lost_registration_response_not_detected")
        if (
            sql_scalar(f"select state from public.public_releases where id='{first_release_id}'")
            != "deployed_unrecorded"
        ):
            raise AssertionError("uploaded_release_not_marked_unrecorded")
        reconcile(
            rpc=rpc,
            pages=pages,
            release_id=first_release_id,
            deployment_id=first.production_deployment_id,
            digest=first_digest,
        )
        if (
            sql_scalar("select active_release_id::text from private.deployment_state")
            != first_release_id
        ):
            raise AssertionError("first_release_not_current_after_reconcile")

        second_release_id, second_artifact = create_second_release(store, first_release_id, keys)
        if (
            sql_scalar("select active_release_id::text from private.deployment_state")
            != first_release_id
        ):
            raise AssertionError("build_replaced_current_deployment")
        second = publish(
            rpc=rpc,
            pages=pages,
            artifact=second_artifact,
            release_id=second_release_id,
            commit_sha="b" * 40,
        )
        if second.reconciliation_required:
            raise AssertionError("second_release_registration_failed")
        try:
            rpc.mark_deploying(first_release_id, first_digest, "a" * 40)
        except HTTPError as error:
            reason = json.loads(error.read()).get("message")
            if reason != "older_release_cannot_overwrite_newer":
                raise
        else:
            raise AssertionError("older_release_was_allowed_to_replace_newer")
        restored_deployment_id = pages.rollback(first.production_deployment_id, first_digest)
        if pages.release_id(restored_deployment_id) != first_release_id:
            raise AssertionError("restored_pages_artifact_release_mismatch")
        rpc.record_rollback(
            target_release_id=first_release_id,
            expected_active_release_id=second_release_id,
            expected_active_deployment_id=second.production_deployment_id,
            rollback_deployment_id=restored_deployment_id,
            digest=first_digest,
            reason_code="synthetic_technical_rollback",
        )
        if (
            sql_scalar("select active_release_id::text from private.deployment_state")
            != first_release_id
        ):
            raise AssertionError("original_artifact_not_current_after_rollback")
        if sql_scalar("select count(*) from private.deployment_receipts") != "3":
            raise AssertionError("deployment_audit_receipt_count_mismatch")
        if (
            store.call("export_public_release", {"p_release_id": first_release_id})
            != initial_export
        ):
            raise AssertionError("rollback_modified_immutable_release")

        # A third upload fails smoke before it is recorded as active. Pages
        # restores the original bytes, then SQL closes the unrecorded attempt.
        failed_release_id, failed_artifact = create_second_release(store, first_release_id, keys)
        failed_digest = artifact_hash(failed_artifact)
        rpc.mark_deploying(failed_release_id, failed_digest, "c" * 40)
        failed_deployment_id = pages.upload("production", failed_release_id, failed_digest)
        rpc.note_uploaded(failed_release_id, failed_deployment_id, failed_digest)
        if (
            sql_scalar(f"select state from public.public_releases where id='{failed_release_id}'")
            != "deployed_unrecorded"
        ):
            raise AssertionError("failed_smoke_upload_not_preserved")
        restored_again = pages.rollback(first.production_deployment_id, first_digest)
        if pages.release_id(restored_again) != first_release_id:
            raise AssertionError("failed_smoke_pages_restore_mismatch")
        try:
            rpc.record_unrecorded_upload_rollback(
                failed_release_id=failed_release_id,
                failed_deployment_id=failed_deployment_id,
                expected_active_release_id=first_release_id,
                expected_active_deployment_id=restored_deployment_id,
                restored_deployment_id=restored_again,
                restored_artifact_hash="f" * 64,
                reason_code="synthetic_smoke_failure",
            )
        except HTTPError as error:
            if json.loads(error.read()).get("message") != "unrecorded_rollback_receipt_invalid":
                raise
        else:
            raise AssertionError("wrong_restored_hash_accepted")
        rpc.record_unrecorded_upload_rollback(
            failed_release_id=failed_release_id,
            failed_deployment_id=failed_deployment_id,
            expected_active_release_id=first_release_id,
            expected_active_deployment_id=restored_deployment_id,
            restored_deployment_id=restored_again,
            restored_artifact_hash=first_digest,
            reason_code="synthetic_smoke_failure",
        )
        if (
            sql_scalar(f"select state from public.public_releases where id='{failed_release_id}'")
            != "upload_rolled_back"
            or sql_scalar("select active_deployment_id from private.deployment_state")
            != restored_again
            or sql_scalar("select count(*) from private.deployment_receipts") != "5"
        ):
            raise AssertionError("unrecorded_upload_withdrawal_not_persisted")
    print(
        "GREEN real local PostgreSQL + localhost Pages: upload-unrecorded → "
        "reconcile → new release → older-version rejection → original artifact rollback "
        "→ failed smoke upload withdrawal"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
