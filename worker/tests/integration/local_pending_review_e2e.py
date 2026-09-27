"""A pending update defers a new matching item without burning its retry budget."""

from __future__ import annotations

from uuid import uuid4

from local_existing_pattern_e2e import main as create_existing_proposal
from local_existing_pattern_e2e import review_pending_update
from local_pipeline_e2e import (
    LOCAL_API,
    ROOT,
    LocalSourceTransport,
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


def main() -> int:
    create_existing_proposal()
    key = f"local-deferred-{uuid4().hex[:10]}"
    source = {
        "key": key,
        "display_name": "隔离本地待审冲突来源",
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
        for attempt in range(2):
            result = pipeline.run(**parameters)
            if (
                result["outcome"] != "degraded"
                or result["counts"].get("pending_review_deferred") != 1
                or result["counts"].get("analysis_failures", 0)
            ):
                raise AssertionError(f"pending_review_not_deferred:{attempt}:{result}")
            state = sql_scalar(
                "select version.processing_status || ':' || version.attempt_count || ':' || "
                "version.last_error from public.source_item_versions as version "
                "join public.source_items as item on item.id=version.source_item_id "
                "join public.sources as source on source.id=item.source_id "
                f"where source.source_key='{key}'"
            )
            if state != "pending_ai:0:pending_review_conflict":
                raise AssertionError(f"pending_review_consumed_retry:{state}")
        if calls["comparison"] != 1:
            raise AssertionError("pending_review_repeated_model_comparison")
        review_pending_update("approve")
        resumed = pipeline.run(**parameters)
        if resumed["outcome"] != "success" or resumed["counts"].get("review_items") != 1:
            raise AssertionError(f"deferred_update_did_not_resume:{resumed}")
        review_pending_update("reject")
        receipt_count = sql_scalar(
            "select count(*) from public.source_version_updates as update_item "
            "join public.source_item_versions as version "
            "on version.id=update_item.source_item_version_id "
            "join public.source_items as item on item.id=version.source_item_id "
            "join public.sources as source on source.id=item.source_id "
            f"where source.source_key='{key}'"
        )
        if receipt_count != "1":
            raise AssertionError("deferred_update_duplicate_receipt")
        print(
            "GREEN pending update deferred twice without retry loss; "
            "approved then resumed and rejected"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
