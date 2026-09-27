"""Exercise an existing-pattern evidence proposal in disposable local PostgreSQL."""

from __future__ import annotations

import argparse
import os
import secrets
from uuid import uuid4

from local_pipeline_e2e import (
    LOCAL_API,
    ROOT,
    LocalSourceTransport,
    _post_json,
    local_keys,
    protocol_server,
    review_in_browser,
    sql_scalar,
)

from scam_radar.collectors.http import BoundedHttpTransport
from scam_radar.collectors.source import SourceCollector
from scam_radar.durable import DurablePipeline
from scam_radar.llm.http_provider import HttpModelProvider
from scam_radar.policy.engine import load_publication_policy
from scam_radar.storage.rpc import RpcStore


def review_pending_update(decision: str) -> None:
    pending = sql_scalar(
        "select update_item.pattern_id::text || ':' || "
        "pattern.latest_approved_revision_id::text || ':' || "
        "base.content_hash || ':' || update_item.revision_id::text || ':' || "
        "update_item.evidence_id::text || ':' || update_item.review_item_id::text "
        "from public.source_version_updates as update_item "
        "join public.scam_patterns as pattern on pattern.id=update_item.pattern_id "
        "join public.pattern_revisions as base "
        "on base.id=pattern.latest_approved_revision_id "
        "join public.review_items as review on review.id=update_item.review_item_id "
        "where review.status='pending' order by review.created_at desc limit 1"
    )
    if not pending:
        raise AssertionError("local_pending_update_required")
    pattern_id, base_id, base_hash, revision_id, evidence_id, review_id = pending.split(":")
    keys = local_keys()
    auth_http = BoundedHttpTransport(allowed_origins={LOCAL_API}, min_interval=0, max_requests=8)
    email = f"local-update-reviewer-{uuid4().hex[:12]}@example.invalid"
    password = secrets.token_urlsafe(24)
    created = _post_json(
        auth_http,
        LOCAL_API + "/auth/v1/admin/users",
        {"email": email, "password": password, "email_confirm": True},
        apikey=keys["service"],
        bearer=keys["service"],
    )
    sql_scalar(
        "insert into public.admin_users(user_id,role,enabled) values "
        f"('{created['id']}','reviewer',true) returning user_id"
    )
    old_decision = os.environ.get("SCAM_RADAR_REVIEW_DECISION")
    os.environ["SCAM_RADAR_REVIEW_DECISION"] = decision
    try:
        review_in_browser(email, password, keys["anon"], script="check-update-browser.mjs")
    finally:
        if old_decision is None:
            os.environ.pop("SCAM_RADAR_REVIEW_DECISION", None)
        else:
            os.environ["SCAM_RADAR_REVIEW_DECISION"] = old_decision
    state = sql_scalar(
        "select review.status || ':' || evidence.acceptance_status || ':' || "
        "revision.revision_status || ':' || "
        "coalesce(pattern.current_draft_revision_id::text,'<empty>') || ':' || "
        "pattern.latest_approved_revision_id::text || ':' || base.content_hash "
        "from public.review_items as review "
        f"join public.pattern_evidence as evidence on evidence.id='{evidence_id}' "
        f"join public.pattern_revisions as revision on revision.id='{revision_id}' "
        f"join public.scam_patterns as pattern on pattern.id='{pattern_id}' "
        f"join public.pattern_revisions as base on base.id='{base_id}' "
        f"where review.id='{review_id}'"
    )
    status, evidence_status, revision_status, draft_id, latest_id, unchanged_hash = state.split(":")
    if unchanged_hash != base_hash or draft_id != "<empty>":
        raise AssertionError("local_update_changed_approved_base_or_kept_draft")
    if decision == "approve":
        if (status, evidence_status, revision_status, latest_id) != (
            "approved",
            "accepted",
            "approved",
            revision_id,
        ):
            raise AssertionError(f"local_update_approval_incomplete:{state}")
    elif (status, evidence_status, revision_status, latest_id) != (
        "rejected",
        "rejected",
        "rejected",
        base_id,
    ):
        raise AssertionError(f"local_update_rejection_incomplete:{state}")
    print(f"GREEN local browser {decision} existing evidence; base immutable, draft released")


def main(*, decision: str | None = None, review_pending: bool = False) -> int:
    if review_pending:
        if decision is None:
            raise ValueError("review_decision_required")
        review_pending_update(decision)
        return 0
    key = f"local-existing-{uuid4().hex[:10]}"
    source = {
        "key": key,
        "display_name": "隔离本地追加来源",
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
    with protocol_server(existing_update=True) as (origin, calls):
        store = RpcStore(
            transport=BoundedHttpTransport(
                allowed_origins={LOCAL_API}, min_interval=0, max_requests=250
            ),
            base_url=LOCAL_API,
            token=local_keys()["service"],
        )
        provider = HttpModelProvider(
            root=ROOT,
            transport=BoundedHttpTransport(
                allowed_origins={origin}, min_interval=0, max_requests=20
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
        if first["outcome"] != "success" or first["counts"].get("review_items") != 1:
            raise AssertionError(f"local_existing_proposal_failed:{first}")
        if calls["comparison"] != 1:
            raise AssertionError(f"local_existing_comparison_missing:{calls}")
        proposal = sql_scalar(
            "select count(*) || ':' || count(distinct update.review_item_id) "
            "from public.source_version_updates as update "
            "join public.source_item_versions as version "
            "on version.id=update.source_item_version_id "
            "join public.source_items as item on item.id=version.source_item_id "
            "join public.sources as source on source.id=item.source_id "
            f"where source.source_key='{key}'"
        )
        if proposal != "1:1":
            raise AssertionError(f"local_existing_proposal_not_durable:{proposal}")
        before = calls["model"]
        repeated = pipeline.run(**parameters)
        if repeated["outcome"] != "success" or repeated["counts"].get("review_items", 0):
            raise AssertionError(f"local_existing_replay_failed:{repeated}")
        if calls["model"] != before:
            raise AssertionError("local_existing_replay_called_model")
        print("GREEN local existing-pattern proposal: one evidence/review, cached repeat")
    if decision is not None:
        review_pending_update(decision)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", choices=["approve", "reject"])
    parser.add_argument("--review-pending", action="store_true")
    options = parser.parse_args()
    raise SystemExit(main(decision=options.decision, review_pending=options.review_pending))
