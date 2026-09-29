"""Resume an actual existing-pattern proposal after a separate worker exits."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
from uuid import uuid4

from local_existing_pattern_e2e import review_pending_update
from local_pipeline_e2e import (
    LOCAL_API,
    ROOT,
    LocalSourceTransport,
    _post_json,
    local_keys,
    protocol_server,
    sql_scalar,
)

from scam_radar.collectors.http import BoundedHttpTransport
from scam_radar.collectors.source import SourceCollector
from scam_radar.durable import DurablePipeline
from scam_radar.llm.http_provider import HttpModelProvider
from scam_radar.policy.engine import load_publication_policy
from scam_radar.storage.rpc import RpcStore


def source_for(key: str) -> dict[str, object]:
    return {
        "key": key,
        "display_name": "隔离进程中断来源",
        "publisher_group": key,
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


class FaultStore(RpcStore):
    def __init__(self, *, fault: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.fault = fault

    def submit_existing_evidence(self, **kwargs: object) -> dict[str, object]:
        receipt = super().submit_existing_evidence(**kwargs)  # type: ignore[arg-type]
        if self.fault == "after_submit":
            os._exit(73)
        if self.fault == "lost_submit_response":
            raise RuntimeError("injected_response_lost_after_commit")
        return receipt

    def record_policy(self, **kwargs: object) -> str:
        receipt = super().record_policy(**kwargs)  # type: ignore[arg-type]
        if self.fault == "after_policy":
            os._exit(74)
        return receipt

    def finish_version(
        self, version_id: str, holder: str, status: str, error_code: str | None = None
    ) -> None:
        if self.fault == "before_finish" and status == "processed":
            os._exit(75)
        super().finish_version(version_id, holder, status, error_code)


def run_worker(key: str, origin: str, fault: str) -> int:
    store = FaultStore(
        fault=fault,
        transport=BoundedHttpTransport(
            allowed_origins={LOCAL_API}, min_interval=0, max_requests=250
        ),
        base_url=LOCAL_API,
        token=local_keys()["service"],
    )
    provider = HttpModelProvider(
        root=ROOT,
        transport=BoundedHttpTransport(allowed_origins={origin}, min_interval=0, max_requests=20),
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
    result = pipeline.run(
        sources=[source_for(key)],
        commit_sha="a" * 40,
        registry_hash="b" * 64,
        behavior_hash="c" * 64,
    )
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


def snapshot(key: str) -> tuple[str, ...]:
    value = sql_scalar(
        "select v.id::text || '|' || v.processing_status || '|' || v.attempt_count || '|' || "
        "coalesce(v.last_error,'none') || '|' || "
        "coalesce(state.cursor_value,'<empty>') || '|' || "
        "count(distinct u.evidence_id) || '|' || count(distinct u.revision_id) || '|' || "
        "count(distinct u.review_item_id) || '|' || count(distinct p.id) "
        "from public.source_item_versions v "
        "join public.source_items i on i.id=v.source_item_id "
        "join public.sources s on s.id=i.source_id "
        "left join public.source_states state on state.source_id=s.id "
        "left join public.source_version_updates u on u.source_item_version_id=v.id "
        "left join public.policy_decisions p on p.review_item_id=u.review_item_id "
        f"where s.source_key='{key}' group by v.id,state.cursor_value"
    )
    if not value:
        raise AssertionError("crash_version_missing")
    return tuple(value.split("|"))


def receipt_ids(key: str) -> tuple[str, ...]:
    value = sql_scalar(
        "select u.pattern_id::text || '|' || u.revision_id::text || '|' || "
        "u.evidence_id::text || '|' || u.review_item_id::text || '|' || "
        "coalesce(p.id::text,'<empty>') || '|' || r.status "
        "from public.source_version_updates u "
        "join public.source_item_versions v on v.id=u.source_item_version_id "
        "join public.source_items i on i.id=v.source_item_id "
        "join public.sources s on s.id=i.source_id "
        "join public.review_items r on r.id=u.review_item_id "
        "left join public.policy_decisions p on p.review_item_id=u.review_item_id "
        f"where s.source_key='{key}'"
    )
    if not value:
        raise AssertionError("committed_receipt_ids_missing")
    return tuple(value.split("|"))


def child(key: str, origin: str, fault: str) -> dict[str, object] | None:
    completed = subprocess.run(
        [sys.executable, __file__, "--child", key, origin, fault],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    expected = {"after_submit": 73, "after_policy": 74, "before_finish": 75}.get(fault, 0)
    if completed.returncode != expected:
        raise AssertionError(
            f"unexpected_worker_exit:{fault}:{completed.returncode}:"
            f"{completed.stdout[-200:]}:{completed.stderr[-200:]}"
        )
    return json.loads(completed.stdout) if completed.stdout else None


def expire_claim(key: str) -> None:
    sql_scalar(
        "update public.source_item_versions set claimed_until=now()-interval '1 second' "
        "where id in (select v.id from public.source_item_versions v "
        "join public.source_items i on i.id=v.source_item_id "
        "join public.sources s on s.id=i.source_id "
        f"where s.source_key='{key}') returning id"
    )
    sql_scalar(
        "update public.operation_leases set acquired_at=now()-interval '2 seconds', "
        "expires_at=now()-interval '1 second' "
        f"where lease_key='source:{key}' returning lease_key"
    )


def reviewer_rpc(key: str, decision: str) -> None:
    if decision not in {"hold", "reject"}:
        raise ValueError("invalid_test_review_decision")
    review = sql_scalar(
        "select review.id::text || '|' || review.candidate_hash "
        "from public.source_version_updates as update_item "
        "join public.review_items as review on review.id=update_item.review_item_id "
        "join public.source_item_versions as version "
        "on version.id=update_item.source_item_version_id "
        "join public.source_items as item on item.id=version.source_item_id "
        "join public.sources as source on source.id=item.source_id "
        f"where source.source_key='{key}'"
    )
    review_id, candidate_hash = review.split("|")
    keys = local_keys()
    http = BoundedHttpTransport(allowed_origins={LOCAL_API}, min_interval=0, max_requests=8)
    email = f"local-hold-reviewer-{uuid4().hex[:12]}@example.invalid"
    password = secrets.token_urlsafe(24)
    created = _post_json(
        http,
        LOCAL_API + "/auth/v1/admin/users",
        {"email": email, "password": password, "email_confirm": True},
        apikey=keys["service"],
        bearer=keys["service"],
    )
    sql_scalar(
        "insert into public.admin_users(user_id,role,enabled) values "
        f"('{created['id']}','reviewer',true) returning user_id"
    )
    session = _post_json(
        http,
        LOCAL_API + "/auth/v1/token?grant_type=password",
        {"email": email, "password": password},
        apikey=keys["anon"],
        bearer=keys["anon"],
    )
    _post_json(
        http,
        LOCAL_API
        + (
            "/rest/v1/rpc/hold_for_evidence"
            if decision == "hold"
            else "/rest/v1/rpc/reject_review_item"
        ),
        {
            "p_review_item_id": review_id,
            "p_expected_candidate_hash": candidate_hash,
            "p_decision_note": "Synthetic reviewer decision for recovery test",
        },
        apikey=keys["anon"],
        bearer=session["access_token"],
    )


def main() -> int:
    with protocol_server(existing_update=True) as (origin, calls):
        for fault, pre_review, post_review in (
            ("after_submit", None, "reject"),
            ("after_submit", "reject", None),
            ("after_policy", "approve", None),
            ("after_policy", "reject", None),
            ("lost_submit_response", None, "reject"),
        ):
            key = f"local-crash-{uuid4().hex[:10]}"
            early_reject = fault == "after_submit" and pre_review == "reject"
            first = child(key, origin, fault)
            before = snapshot(key)
            original_ids = receipt_ids(key)
            initial_policy_count = "1" if fault == "after_policy" else "0"
            initial_status = "error" if fault == "lost_submit_response" else "processing"
            if (
                before[1] != initial_status
                or before[4] != "<empty>"
                or before[5:] != ("1", "1", "1", initial_policy_count)
                or (original_ids[4] == "<empty>" and fault == "after_policy")
            ):
                raise AssertionError(f"committed_receipt_missing_before_recovery:{fault}:{before}")
            if fault == "lost_submit_response" and (
                first is None or first["outcome"] != "degraded"
            ):
                raise AssertionError(f"lost_response_failure_not_recorded:{first}")
            if fault != "lost_submit_response":
                expire_claim(key)
            if pre_review is not None:
                review_pending_update(pre_review)
                reviewed_ids = receipt_ids(key)
                if reviewed_ids[:5] != original_ids[:5] or reviewed_ids[5] != (
                    "approved" if pre_review == "approve" else "rejected"
                ):
                    raise AssertionError("human_decision_changed_receipt")
            model_calls_before = calls["model"]
            reviewed_status = receipt_ids(key)[5]
            resumed = child(key, origin, "none")
            after = snapshot(key)
            recovered_ids = receipt_ids(key)
            if resumed is None or resumed["outcome"] != "success":
                raise AssertionError(f"committed_receipt_did_not_resume:{fault}:{resumed}:{after}")
            if (
                after[0] != before[0]
                or after[1] != "processed"
                or after[4] == "<empty>"
                or after[5:] != ("1", "1", "1", "0" if early_reject else "1")
                or recovered_ids[:4] != original_ids[:4]
                or recovered_ids[5] != reviewed_status
                or calls["model"] != model_calls_before
            ):
                raise AssertionError(f"committed_receipt_recovery_side_effects:{fault}:{after}")
            if original_ids[4] != "<empty>" and recovered_ids[4] != original_ids[4]:
                raise AssertionError("recorded_policy_duplicated_on_resume")
            repeated = child(key, origin, "none")
            if (
                repeated is None
                or repeated["outcome"] != "success"
                or snapshot(key) != after
                or receipt_ids(key) != recovered_ids
                or calls["model"] != model_calls_before
            ):
                raise AssertionError("committed_receipt_repeat_changed_database")
            competing_key = None
            if fault == "after_submit" and pre_review is None:
                competing_key = f"local-conflict-{uuid4().hex[:10]}"
                competing = child(competing_key, origin, "none")
                conflict_state = snapshot(competing_key)
                if (
                    competing is None
                    or competing["outcome"] != "degraded"
                    or competing["counts"].get("pending_review_deferred") != 1
                    or conflict_state[1:4] != ("pending_ai", "0", "pending_review_conflict")
                    or conflict_state[5:] != ("0", "0", "0", "0")
                ):
                    raise AssertionError(f"other_source_conflict_not_deferred:{competing}")
            if post_review is not None:
                review_pending_update(post_review)
                if receipt_ids(key)[:5] != recovered_ids[:5]:
                    raise AssertionError("review_after_recovery_changed_receipt")
            if competing_key is not None:
                competing_resumed = child(competing_key, origin, "none")
                if (
                    competing_resumed is None
                    or competing_resumed["outcome"] != "success"
                    or snapshot(competing_key)[5:] != ("1", "1", "1", "1")
                ):
                    raise AssertionError("other_source_conflict_did_not_resume")
                review_pending_update("reject")
            print(
                f"GREEN {fault}/{pre_review or 'unreviewed'}: "
                f"one receipt, {0 if early_reject else 1} Policy, processed once"
            )
        held_key = f"local-held-crash-{uuid4().hex[:10]}"
        child(held_key, origin, "after_submit")
        held_original = receipt_ids(held_key)
        expire_claim(held_key)
        reviewer_rpc(held_key, "hold")
        if (
            receipt_ids(held_key)[:5] != held_original[:5]
            or receipt_ids(held_key)[5] != "needs_evidence"
        ):
            raise AssertionError("human_hold_changed_receipt")
        held_model_calls = calls["model"]
        resumed_hold = child(held_key, origin, "none")
        held_final = snapshot(held_key)
        held_ids = receipt_ids(held_key)
        if (
            resumed_hold is None
            or resumed_hold["outcome"] != "success"
            or held_final[1] != "processed"
            or held_final[4] == "<empty>"
            or held_final[5:] != ("1", "1", "1", "1")
            or held_ids[:4] != held_original[:4]
            or held_ids[5] != "needs_evidence"
            or calls["model"] != held_model_calls
        ):
            raise AssertionError(f"held_update_policy_did_not_resume:{resumed_hold}:{held_final}")
        review_pending_update("approve")
        approved_ids = receipt_ids(held_key)
        if approved_ids[:5] != held_ids[:5] or approved_ids[5] != "approved":
            raise AssertionError("held_human_approval_changed_receipt")
        repeated_hold = child(held_key, origin, "none")
        if (
            repeated_hold is None
            or repeated_hold["outcome"] != "success"
            or snapshot(held_key) != held_final
            or receipt_ids(held_key) != approved_ids
            or calls["model"] != held_model_calls
        ):
            raise AssertionError("held_approved_update_repeat_changed_database")
        print("GREEN held update: delayed Policy, human approval, same receipt")
        legacy_key = f"local-legacy-held-{uuid4().hex[:10]}"
        child(legacy_key, origin, "after_submit")
        legacy_original = receipt_ids(legacy_key)
        expire_claim(legacy_key)
        reviewer_rpc(legacy_key, "hold")
        sql_scalar(
            "update public.scam_patterns set row_version=row_version+1 "
            "where id=(select update_item.pattern_id "
            "from public.source_version_updates as update_item "
            "join public.source_item_versions as version "
            "on version.id=update_item.source_item_version_id "
            "join public.source_items as item on item.id=version.source_item_id "
            "join public.sources as source on source.id=item.source_id "
            f"where source.source_key='{legacy_key}') returning row_version"
        )
        legacy_model_calls = calls["model"]
        for _ in range(2):
            held = child(legacy_key, origin, "none")
            state = snapshot(legacy_key)
            if (
                held is None
                or held["outcome"] != "degraded"
                or held["counts"].get("evidence_review_deferred") != 1
                or held["counts"].get("analysis_failures", 0) != 0
                or state[1:5] != ("pending_ai", "1", "awaiting_evidence_review", "<empty>")
                or state[5:] != ("1", "1", "1", "0")
                or receipt_ids(legacy_key)[5] != "needs_evidence"
                or calls["model"] != legacy_model_calls
            ):
                raise AssertionError(f"legacy_held_update_retry_was_consumed:{held}:{state}")
        reviewer_rpc(legacy_key, "reject")
        if receipt_ids(legacy_key)[5] != "rejected":
            raise AssertionError("legacy_held_human_rejection_missing")
        resumed_legacy = child(legacy_key, origin, "none")
        legacy_final = snapshot(legacy_key)
        if (
            resumed_legacy is None
            or resumed_legacy["outcome"] != "success"
            or legacy_final[1] != "processed"
            or legacy_final[4] == "<empty>"
            or legacy_final[5:] != ("1", "1", "1", "0")
            or receipt_ids(legacy_key)[:5] != legacy_original[:5]
            or receipt_ids(legacy_key)[5] != "rejected"
            or calls["model"] != legacy_model_calls
        ):
            raise AssertionError(
                f"legacy_held_rejection_did_not_resume:{resumed_legacy}:{legacy_final}"
            )
        restored_lifecycle = sql_scalar(
            "select pattern.lifecycle_status from public.source_version_updates as update_item "
            "join public.source_item_versions as version "
            "on version.id=update_item.source_item_version_id "
            "join public.source_items as item on item.id=version.source_item_id "
            "join public.sources as source on source.id=item.source_id "
            "join public.scam_patterns as pattern on pattern.id=update_item.pattern_id "
            f"where source.source_key='{legacy_key}'"
        )
        if restored_lifecycle != "review_ready":
            raise AssertionError(f"held_rejection_hid_approved_pattern:{restored_lifecycle}")
        print(
            "GREEN legacy held update deferred without retry loss, then rejection restored pattern"
        )
        repeated_key = f"local-repeat-crash-{uuid4().hex[:10]}"
        original_ids: tuple[str, ...] | None = None
        for attempt in range(3):
            child(repeated_key, origin, "before_finish")
            state = snapshot(repeated_key)
            ids = receipt_ids(repeated_key)
            if state[1] != "processing" or state[5:] != ("1", "1", "1", "1"):
                raise AssertionError(f"repeated_crash_lost_transaction:{attempt}:{state}")
            if original_ids is not None and ids != original_ids:
                raise AssertionError("repeated_crash_duplicated_receipt_or_policy")
            original_ids = ids
            expire_claim(repeated_key)
        recovered = child(repeated_key, origin, "none")
        final_state = snapshot(repeated_key)
        if (
            recovered is None
            or recovered["outcome"] != "success"
            or final_state[1] != "processed"
            or final_state[5:] != ("1", "1", "1", "1")
            or receipt_ids(repeated_key) != original_ids
        ):
            raise AssertionError(f"repeated_crash_permanently_stuck:{recovered}:{final_state}")
        review_pending_update("reject")
        print("GREEN three repeated process exits before finish recovered once")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", nargs=3, metavar=("KEY", "ORIGIN", "FAULT"))
    args = parser.parse_args()
    raise SystemExit(run_worker(*args.child) if args.child else main())
