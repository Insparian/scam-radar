"""Publish a human-approved evidence update as one exact immutable local release."""

from __future__ import annotations

import json
import subprocess
import sys
from uuid import UUID

from local_deployment_e2e import DropFirstRecord
from local_pipeline_e2e import LOCAL_API, ROOT, local_keys, sql_scalar

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


def main() -> int:
    if not LOCAL_API.startswith("http://127.0.0.1:"):
        raise RuntimeError("isolated_local_api_required")
    first_id = sql_scalar(
        "select id::text from public.public_releases where state in ('approved','deployed') "
        "order by release_no desc limit 1"
    )
    first_artifact = ROOT / "work/launch-readiness/joined-e2e" / first_id / "site"
    first_hash = artifact_hash(first_artifact)
    keys = local_keys()
    store = RpcStore(
        transport=BoundedHttpTransport(
            allowed_origins={LOCAL_API}, min_interval=0, max_requests=100
        ),
        base_url=LOCAL_API,
        token=keys["service"],
    )
    rpc = LocalPostgrestReleaseRpc(LOCAL_API, keys["service"])
    first_export = store.call("export_public_release", {"p_release_id": first_id})
    old_revision = sql_scalar(
        "select pattern_revision_id::text from public.public_release_items "
        f"where release_id='{first_id}'"
    )
    latest_revision = sql_scalar(
        "select pattern.latest_approved_revision_id::text "
        "from public.scam_patterns as pattern "
        "join public.public_release_items as item on item.pattern_id=pattern.id "
        f"where item.release_id='{first_id}'"
    )
    if old_revision == latest_revision:
        raise AssertionError("approved_existing_update_required")
    with RehearsalServer(first_id, first_hash) as server:
        pages = LocalPages(JsonHttp(server.origin))
        first_state = sql_scalar(f"select state from public.public_releases where id='{first_id}'")
        if first_state == "approved":
            dropped = DropFirstRecord(rpc)
            first = publish(
                rpc=dropped,
                pages=pages,
                artifact=first_artifact,
                release_id=first_id,
                commit_sha="a" * 40,
            )
            if not first.reconciliation_required or not dropped.failed:
                raise AssertionError("lost_first_registration_not_detected")
            reconcile(
                rpc=rpc,
                pages=pages,
                release_id=first_id,
                deployment_id=first.production_deployment_id,
                digest=first_hash,
            )
        elif first_state != "deployed":
            raise AssertionError(f"first_release_not_deployable:{first_state}")
        second_id = str(
            UUID(
                store.call(
                    "prepare_public_release",
                    {"p_expected_previous_release_id": first_id},
                )
            )
        )
        exported = store.call("export_public_release", {"p_release_id": second_id})
        mapped = map_database_release(exported, second_id)
        if len(mapped["patterns"]) != 1:
            raise AssertionError("updated_release_pattern_count_changed")
        second_revision = sql_scalar(
            "select pattern_revision_id::text from public.public_release_items "
            f"where release_id='{second_id}'"
        )
        if second_revision != latest_revision or second_revision == old_revision:
            raise AssertionError("updated_release_did_not_pin_approved_revision")
        output = ROOT / "work/launch-readiness/update-release" / second_id
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
                second_id,
                "--destination",
                str(output / "site"),
            ],
            cwd=ROOT,
            check=True,
        )
        second_artifact = output / "site"
        second = publish(
            rpc=rpc,
            pages=pages,
            artifact=second_artifact,
            release_id=second_id,
            commit_sha="b" * 40,
        )
        if (
            second.reconciliation_required
            or pages.release_id(second.production_deployment_id) != second_id
        ):
            raise AssertionError("updated_release_not_deployed_locally")
        if (
            sql_scalar("select active_release_id::text from private.deployment_state") != second_id
            or artifact_hash(first_artifact) != first_hash
            or store.call("export_public_release", {"p_release_id": first_id}) != first_export
        ):
            raise AssertionError("updated_release_changed_original")
    subprocess.run(
        [
            "node",
            "scripts/check-release-browser.mjs",
            str(second_artifact),
            second_id,
            str(output / "browser"),
            "1",
        ],
        cwd=ROOT / "web",
        check=True,
    )
    print("GREEN existing evidence → immutable updated release → local Pages → 4-width browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
