"""Narrow Supabase RPC client. No generic table access or browser credential use."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from scam_radar.collectors.http import BoundedHttpTransport
from scam_radar.domain import NormalizedItem


class RpcStore:
    def __init__(self, *, transport: BoundedHttpTransport, base_url: str, token: str) -> None:
        transport.validate_url(base_url)
        self.transport, self.base_url, self.token = transport, base_url.rstrip("/"), token

    def call(self, name: str, parameters: dict[str, Any]) -> Any:
        if not re.fullmatch(r"[a-z][a-z0-9_]+", name):
            raise ValueError("invalid_rpc_name")
        response = self.transport.request(
            f"{self.base_url}/rest/v1/rpc/{name}",
            method="POST",
            body=json.dumps(parameters).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "apikey": self.token,
                "Content-Type": "application/json",
            },
            retries=0,
        )
        return json.loads(response.body) if response.body else None

    def ingest(self, item: NormalizedItem) -> str:
        result = self.call(
            "ingest_source_version",
            {
                "p_source_key": item.source_key,
                "p_identity_key": item.identity_key,
                "p_url": str(item.canonical_url),
                "p_title": item.title,
                "p_clean_text": item.clean_text,
                "p_content_hash": item.content_hash,
                "p_published_at": item.published_at.isoformat() if item.published_at else None,
                "p_text_truncated": item.text_truncated,
            },
        )
        if not isinstance(result, str):
            raise ValueError("invalid_ingestion_receipt")
        return result

    @staticmethod
    def _uuid(value: Any, receipt: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"invalid_{receipt}")
        return str(UUID(value))

    def sync_source(self, source: dict[str, Any]) -> str:
        canonical = json.dumps(source, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        config_hash = hashlib.sha256(canonical.encode()).hexdigest()
        policy = source["policy"]
        collector = source["collector"]
        parser = source["parser"]
        result = self.call(
            "sync_registry_source",
            {
                "p_source_key": source["key"],
                "p_name": source["display_name"],
                "p_domain": urlsplit(collector["entry_url"]).hostname,
                "p_publisher_group": source["publisher_group"],
                "p_source_type": source["source_type"],
                "p_authority_tier": source["authority_tier"],
                "p_ingestion_method": (
                    "html_polling" if collector["type"] == "html" else collector["type"]
                ),
                "p_entry_url": collector["entry_url"],
                "p_enabled": source["enabled"],
                "p_collection_allowed": policy["collection_allowed"],
                "p_reviewed_at": policy["reviewed_at"],
                "p_poll_frequency": "manual",
                "p_parser_config": parser["config"],
                "p_config_hash": config_hash,
            },
        )
        return self._uuid(result, "source_sync_receipt")

    def start_run(
        self, *, trigger: str, commit_sha: str, registry_hash: str, behavior_hash: str
    ) -> str:
        result = self.call(
            "start_pipeline_run",
            {
                "p_trigger": trigger,
                "p_commit_sha": commit_sha,
                "p_registry_hash": registry_hash,
                "p_behavior_hash": behavior_hash,
                "p_pipeline_version": "pipeline-v0.1",
            },
        )
        return self._uuid(result, "run_receipt")

    def finish_run(
        self,
        run_id: str,
        *,
        outcome: str,
        discovered: int,
        relevant: int,
        reviews: int,
        error_code: str | None = None,
    ) -> None:
        self.call(
            "finish_pipeline_run",
            {
                "p_run_id": run_id,
                "p_outcome": outcome,
                "p_discovered_count": discovered,
                "p_relevant_count": relevant,
                "p_review_count": reviews,
                "p_error_code": error_code,
            },
        )

    def acquire_lease(self, key: str, holder: str, *, seconds: int = 300) -> bool:
        result = self.call(
            "acquire_operation_lease",
            {"p_lease_key": key, "p_holder_id": holder, "p_ttl_seconds": seconds},
        )
        if not isinstance(result, bool):
            raise ValueError("invalid_lease_receipt")
        return result

    def release_lease(self, key: str, holder: str) -> bool:
        result = self.call(
            "release_operation_lease",
            {"p_lease_key": key, "p_holder_id": holder},
        )
        if not isinstance(result, bool):
            raise ValueError("invalid_lease_release")
        return result

    def claim_version(
        self, source_key: str, holder: str, *, seconds: int = 300
    ) -> dict[str, Any] | None:
        result = self.call(
            "claim_source_version",
            {
                "p_source_key": source_key,
                "p_holder_id": holder,
                "p_lease_seconds": seconds,
            },
        )
        if result is None:
            return None
        if not isinstance(result, dict) or not isinstance(result.get("clean_text"), str):
            raise ValueError("invalid_version_claim")
        self._uuid(result.get("version_id"), "version_claim")
        return result

    def finish_version(
        self, version_id: str, holder: str, status: str, error_code: str | None = None
    ) -> None:
        self.call(
            "finish_source_version",
            {
                "p_version_id": version_id,
                "p_holder_id": holder,
                "p_status": status,
                "p_error_code": error_code,
            },
        )

    def defer_version_for_review(self, version_id: str, holder: str, pattern_id: str) -> None:
        self.call(
            "defer_source_version_for_review",
            {
                "p_version_id": version_id,
                "p_holder_id": holder,
                "p_pattern_id": pattern_id,
            },
        )

    def checkpoint_source(
        self,
        source_key: str,
        run_id: str,
        *,
        success: bool,
        cursor: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.call(
            "record_source_checkpoint",
            {
                "p_source_key": source_key,
                "p_run_id": run_id,
                "p_success": success,
                "p_cursor_value": cursor,
                "p_etag": etag,
                "p_last_modified": last_modified,
                "p_error_code": error_code,
            },
        )

    def get_artifact(
        self,
        *,
        version_id: str,
        stage: str,
        provider: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        input_hash: str,
    ) -> dict[str, Any] | None:
        result = self.call(
            "get_ai_artifact",
            {
                "p_version_id": version_id,
                "p_stage": stage,
                "p_provider": provider,
                "p_model": model,
                "p_prompt_version": prompt_version,
                "p_schema_version": schema_version,
                "p_input_hash": input_hash,
            },
        )
        if result is not None and not isinstance(result, dict):
            raise ValueError("invalid_ai_cache_receipt")
        return result

    def store_artifact(
        self,
        *,
        version_id: str,
        stage: str,
        provider: str,
        model: str,
        prompt_version: str,
        schema_version: str,
        input_hash: str,
        result: dict[str, Any],
        usage: dict[str, Any],
    ) -> str:
        receipt = self.call(
            "store_ai_artifact",
            {
                "p_version_id": version_id,
                "p_stage": stage,
                "p_provider": provider,
                "p_model": model,
                "p_prompt_version": prompt_version,
                "p_schema_version": schema_version,
                "p_input_hash": input_hash,
                "p_result": result,
                "p_usage": usage,
            },
        )
        return self._uuid(receipt, "ai_artifact_receipt")

    def submit_candidate(
        self,
        *,
        version_id: str,
        holder: str,
        run_id: str,
        draft: dict[str, Any],
        spans: list[dict[str, Any]],
        heat: dict[str, Any],
        candidate_payload: dict[str, Any],
        reason_codes: list[str],
    ) -> dict[str, Any]:
        receipt = self.call(
            "submit_new_pattern_candidate",
            {
                "p_version_id": version_id,
                "p_holder_id": holder,
                "p_run_id": run_id,
                "p_draft": draft,
                "p_spans": spans,
                "p_heat": heat,
                "p_candidate_payload": candidate_payload,
                "p_reason_codes": reason_codes,
            },
        )
        if not isinstance(receipt, dict):
            raise ValueError("invalid_candidate_receipt")
        for key in ("pattern_id", "revision_id", "evidence_id", "review_item_id"):
            self._uuid(receipt.get(key), f"candidate_{key}")
        if not isinstance(receipt.get("candidate_hash"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", receipt["candidate_hash"]
        ):
            raise ValueError("invalid_candidate_hash")
        return receipt

    def match_candidates(self, pattern_type: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if not pattern_type or len(pattern_type) > 120 or not 1 <= limit <= 10:
            raise ValueError("invalid_match_candidate_request")
        result = self.call(
            "list_pattern_match_candidates",
            {"p_pattern_type": pattern_type, "p_limit": limit},
        )
        if not isinstance(result, list) or len(result) > limit:
            raise ValueError("invalid_match_candidates")
        for candidate in result:
            if not isinstance(candidate, dict):
                raise ValueError("invalid_match_candidate")
            self._uuid(candidate.get("pattern_id"), "match_pattern_id")
            self._uuid(candidate.get("revision_id"), "match_revision_id")
            if not isinstance(candidate.get("pending_review"), bool):
                raise ValueError("invalid_match_candidate")
            for field in ("canonical_name", "pattern_type", "summary"):
                if not isinstance(candidate.get(field), str) or not candidate[field]:
                    raise ValueError("invalid_match_candidate")
            for field in (
                "impersonated_identities",
                "hooks",
                "pressure_tactics",
                "requested_actions",
                "money_paths",
            ):
                if not isinstance(candidate.get(field), list) or not all(
                    isinstance(value, str) for value in candidate[field]
                ):
                    raise ValueError("invalid_match_candidate")
        return result

    def submit_existing_evidence(
        self,
        *,
        version_id: str,
        holder: str,
        run_id: str,
        pattern_id: str,
        base_revision_id: str,
        claim_summary: str,
        comparison: dict[str, Any],
        heat: dict[str, Any],
        candidate_payload: dict[str, Any],
        reason_codes: list[str],
    ) -> dict[str, Any]:
        receipt = self.call(
            "submit_existing_pattern_evidence",
            {
                "p_version_id": version_id,
                "p_holder_id": holder,
                "p_run_id": run_id,
                "p_pattern_id": pattern_id,
                "p_base_revision_id": base_revision_id,
                "p_claim_summary": claim_summary,
                "p_comparison": comparison,
                "p_heat": heat,
                "p_candidate_payload": candidate_payload,
                "p_reason_codes": reason_codes,
            },
        )
        if not isinstance(receipt, dict):
            raise ValueError("invalid_existing_candidate_receipt")
        for key in ("pattern_id", "revision_id", "evidence_id", "review_item_id"):
            self._uuid(receipt.get(key), f"existing_candidate_{key}")
        if receipt["pattern_id"] != pattern_id:
            raise ValueError("existing_candidate_target_mismatch")
        if not isinstance(receipt.get("candidate_hash"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", receipt["candidate_hash"]
        ):
            raise ValueError("invalid_existing_candidate_hash")
        return receipt

    def record_policy(
        self,
        *,
        review_item_id: str,
        revision_id: str,
        run_id: str,
        policy_version: str,
        policy_hash: str,
        input_hash: str,
        gate_version: str,
        gate_outcome: str,
        rules_outcome: str,
        decision_outcome: str,
        execution_mode: str,
        reason_codes: list[str],
        model_confidence: float | None,
        model_confidence_downgrade: bool,
    ) -> str:
        receipt = self.call(
            "record_policy_decision",
            {
                "p_review_item_id": review_item_id,
                "p_pattern_revision_id": revision_id,
                "p_surface": "public_database",
                "p_policy_version": policy_version,
                "p_policy_hash": policy_hash,
                "p_input_hash": input_hash,
                "p_gate_version": gate_version,
                "p_gate_outcome": gate_outcome,
                "p_rules_outcome": rules_outcome,
                "p_decision_outcome": decision_outcome,
                "p_execution_mode": execution_mode,
                "p_publication_authorized": False,
                "p_model_confidence_downgrade": model_confidence_downgrade,
                "p_reason_codes": reason_codes,
                "p_pipeline_run_id": run_id,
                "p_model_confidence": model_confidence,
            },
        )
        return self._uuid(receipt, "policy_receipt")
