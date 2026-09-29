"""Durable batch orchestration over reviewed sources and narrow database RPCs."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from scam_radar.collectors.source import SourceCollector
from scam_radar.domain import (
    AuthorityTier,
    EvidenceRecord,
    ExtractionResult,
    GateCandidate,
    GateDecision,
    HeatFeatures,
    LegalStatus,
    PatternComparisonResult,
    PolicyInput,
    RelevanceResult,
    RiskType,
)
from scam_radar.evidence.gate import evaluate_evidence
from scam_radar.llm.http_provider import HttpModelProvider
from scam_radar.policy.engine import PublicationPolicy, evaluate_policy
from scam_radar.scoring.heat import calculate_heat
from scam_radar.storage.rpc import RpcStore

ModelResult = TypeVar("ModelResult", bound=BaseModel)


class PendingReviewConflict(Exception):
    def __init__(self, pattern_id: str) -> None:
        super().__init__("pending_review_conflict")
        self.pattern_id = pattern_id


class PendingEvidenceHold(Exception):
    pass


class StageFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _source_classification(source: dict[str, Any], status: LegalStatus) -> tuple[str, str | None]:
    kind, tier = source["source_type"], source["authority_tier"]
    if (
        kind == "police"
        and tier == "A1"
        and status
        in {
            LegalStatus.REPORTED_CASE,
            LegalStatus.ENFORCEMENT,
            LegalStatus.CHARGE,
        }
    ):
        return "confirmed_scam", "警方通报的诈骗案件"
    if kind == "court" and tier == "A1" and status == LegalStatus.JUDGMENT:
        return "confirmed_scam", "司法机关已公开裁判"
    if (
        kind == "regulator"
        and tier in {"A1", "A2"}
        and status
        in {
            LegalStatus.WARNING,
            LegalStatus.ENFORCEMENT,
        }
    ):
        return "risk_alert", "监管部门已提示风险"
    return "risk_alert", None


def _source_claim_type(source: dict[str, Any]) -> str:
    return {
        "police": "official_case",
        "court": "court_record",
        "regulator": "regulator_warning",
        "state_media": "media_report",
        "media": "media_report",
    }[source["source_type"]]


def _draft(
    extraction: ExtractionResult,
    relevance: RelevanceResult,
    clean_text: str,
    seen_at: datetime,
) -> dict[str, Any]:
    first_sentence = clean_text.split("。", 1)[0].split("\n", 1)[0].strip()
    if len(first_sentence) < 4:
        first_sentence = clean_text[:180].strip()
    return {
        "canonical_name": extraction.suspected_pattern_name or "",
        "short_name": extraction.suspected_pattern_name or "",
        "one_sentence_summary": first_sentence[:600],
        "pattern_type": relevance.category or "unknown",
        "legal_status": extraction.official_status.value,
        "target_population": extraction.target_population,
        "contact_channels": extraction.contact_channels,
        "impersonated_identities": [extraction.impersonated_identity]
        if extraction.impersonated_identity
        else [],
        "hooks": [extraction.hook] if extraction.hook else [],
        "pressure_tactics": extraction.pressure_tactics,
        "requested_actions": extraction.requested_actions,
        "money_paths": [extraction.money_path] if extraction.money_path else [],
        "technology_used": extraction.technology_used,
        "warning_signs": extraction.warning_signs,
        "what_to_do": extraction.recommended_actions,
        "regions": extraction.regions,
        "last_material_change_at": (
            seen_at.astimezone(UTC).isoformat() if extraction.case_date == seen_at.date() else None
        ),
    }


def _literal_spans(
    draft: dict[str, Any],
    clean_text: str,
    source: dict[str, Any],
    seen_at: datetime,
    extraction: ExtractionResult,
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    risk_type, label = _source_classification(source, LegalStatus(draft["legal_status"]))
    timestamp = seen_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    claims: dict[str, str] = {
        "canonical_name": draft["canonical_name"],
        "short_name": draft["short_name"],
        "one_sentence_summary": draft["one_sentence_summary"],
        "pattern_type": draft["pattern_type"],
        "legal_status": draft["legal_status"],
        "risk_type": risk_type,
        "first_seen_at": timestamp,
        "last_seen_at": timestamp,
    }
    if label:
        claims["public_evidence_label"] = label
    if draft["last_material_change_at"] is not None:
        claims["last_material_change_at"] = timestamp
    for key, value in draft.items():
        if isinstance(value, list):
            for index, item in enumerate(value, 1):
                claims[f"{key}[{index}]"] = item
    spans: list[dict[str, Any]] = []
    mapped: set[str] = set()
    proposed = {
        span.field_path: span
        for span in extraction.supporting_spans
        if clean_text[span.start : span.end] == span.excerpt
    }
    metadata_fields = {
        "short_name",
        "pattern_type",
        "legal_status",
        "risk_type",
        "public_evidence_label",
        "first_seen_at",
        "last_seen_at",
        "last_material_change_at",
    }
    for field_path, value in claims.items():
        if not value or len(value) > 280:
            continue
        if field_path not in metadata_fields and field_path not in proposed:
            continue
        start = clean_text.find(value)
        if start < 0:
            continue
        if field_path in proposed and value not in proposed[field_path].excerpt:
            continue
        spans.append(
            {
                "field_path": field_path,
                "claim_value": value,
                "start": start,
                "end": start + len(value),
                "excerpt": value,
            }
        )
        mapped.add(field_path)
    return spans, set(claims), mapped


class DurablePipeline:
    def __init__(
        self,
        *,
        store: RpcStore,
        provider: HttpModelProvider,
        policy: PublicationPolicy,
        collector_factory: Callable[[dict[str, Any]], SourceCollector],
        max_items: int = 250,
        max_items_per_source: int = 50,
    ) -> None:
        if not 1 <= max_items <= 250 or not 1 <= max_items_per_source <= 50:
            raise ValueError("invalid_pipeline_limits")
        self.store = store
        self.provider = provider
        self.policy = policy
        self.collector_factory = collector_factory
        self.max_items = max_items
        self.max_items_per_source = max_items_per_source

    def _artifact(
        self,
        version_id: str,
        stage: str,
        clean_text: str,
        result_type: type[ModelResult],
        candidates: list[str] | None = None,
    ) -> ModelResult:
        try:
            input_hash = self.provider.fingerprint(stage, clean_text, candidates)
        except Exception as error:
            raise StageFailure("model_input_failed") from error
        parameters = {
            "version_id": version_id,
            "stage": stage.removesuffix("-v1").replace("pattern-match", "pattern_match"),
            "provider": self.provider.protocol,
            "model": self.provider.model,
            "prompt_version": stage,
            "schema_version": stage,
            "input_hash": input_hash,
        }
        try:
            cached = self.store.get_artifact(**parameters)
        except Exception as error:
            raise StageFailure("artifact_read_failed") from error
        if cached is not None:
            return result_type.model_validate(cached)
        result: BaseModel
        try:
            if stage == "relevance-v1":
                result = self.provider.classify(version_id, clean_text)
            elif stage == "extraction-v1":
                result = self.provider.extract(version_id, clean_text)
            else:
                result = self.provider.compare_patterns(version_id, clean_text, candidates or [])
        except Exception as error:
            code = (
                "model_budget_exhausted"
                if str(error) == "model_call_budget_exhausted"
                else {
                    "relevance-v1": "relevance_model_failed",
                    "extraction-v1": "extraction_model_failed",
                    "pattern-match-v1": "pattern_match_model_failed",
                }[stage]
            )
            raise StageFailure(code) from error
        try:
            validated = result_type.model_validate(result.model_dump(mode="json"))
        except Exception as error:
            raise StageFailure("model_output_validation_failed") from error
        try:
            self.store.store_artifact(
                **parameters,
                result=validated.model_dump(mode="json"),
                usage=self.provider.last_usage,
            )
        except Exception as error:
            raise StageFailure("artifact_write_failed") from error
        return validated

    def _process_claim(
        self, source: dict[str, Any], claim: dict[str, Any], run_id: str
    ) -> tuple[bool, bool]:
        version_id = claim["version_id"]
        clean_text = claim["clean_text"]
        if not isinstance(clean_text, str) or not clean_text:
            raise ValueError("claimed_text_missing")
        try:
            recovery = self.store.get_existing_update_recovery(version_id, run_id)
        except Exception as error:
            raise StageFailure("existing_recovery_read_failed") from error
        if recovery is not None:
            self._complete_recovered_update(version_id, clean_text, run_id, recovery)
            return True, False
        relevance = self._artifact(version_id, "relevance-v1", clean_text, RelevanceResult)
        if not relevance.relevant:
            self.store.finish_version(version_id, run_id, "irrelevant")
            return False, False
        extraction = self._artifact(version_id, "extraction-v1", clean_text, ExtractionResult)
        seen_at = datetime.fromisoformat(
            (claim.get("published_at") or claim["fetched_at"]).replace("Z", "+00:00")
        )
        draft = _draft(extraction, relevance, clean_text, seen_at)
        try:
            candidates = self.store.match_candidates(draft["pattern_type"], limit=8)
        except Exception as error:
            raise StageFailure("candidate_lookup_failed") from error
        comparisons: list[tuple[PatternComparisonResult, dict[str, Any]]] = []
        for candidate in candidates:
            candidate_input = json.dumps(
                candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            comparisons.append(
                (
                    self._artifact(
                        version_id,
                        "pattern-match-v1",
                        clean_text,
                        PatternComparisonResult,
                        [candidate_input],
                    ),
                    candidate,
                )
            )
        matches = [item for item in comparisons if item[0].same_pattern]
        matched: dict[str, Any] | None = None
        if matches:
            comparison, matched = max(matches, key=lambda item: item[0].confidence)
        elif comparisons:
            strongest = max(comparisons, key=lambda item: item[0].confidence)[0]
            comparison = PatternComparisonResult(
                same_pattern=False,
                confidence=strongest.confidence,
                reason_codes=strongest.reason_codes,
                material_change=False,
                changes=["none"],
            )
        else:
            comparison = PatternComparisonResult(
                same_pattern=False,
                confidence=1.0,
                reason_codes=[],
                material_change=False,
                changes=["none"],
            )
        if matched is not None and matched["pending_review"]:
            raise PendingReviewConflict(matched["pattern_id"])
        spans, required, mapped = _literal_spans(draft, clean_text, source, seen_at, extraction)
        risk_type, _ = _source_classification(source, extraction.official_status)
        evidence = EvidenceRecord(
            evidence_id=version_id,
            authority_tier=AuthorityTier(source["authority_tier"]),
            source_claim_type=_source_claim_type(source),  # type: ignore[arg-type]
            origin_group_key=claim["content_hash"],
            evidence_family_id=claim["content_hash"][:32],
            supported_fields=mapped,
        )
        gate = evaluate_evidence(
            GateCandidate(
                risk_type=RiskType(risk_type),
                legal_status=extraction.official_status,
                evidence=[evidence],
                required_public_fields=set() if matched else required,
                mapped_public_fields=set() if matched else mapped,
            )
        )
        as_of = datetime.now(UTC).date()
        material_date = (
            seen_at.date()
            if seen_at.date() <= as_of and (not matched or comparison.material_change)
            else None
        )
        change_set = set(comparison.changes)
        novelty: Literal[
            "new_mechanism",
            "new_technology",
            "new_script_or_step",
            "longstanding_unchanged",
            "unknown",
        ] = "unknown"
        if "new_mechanism" in change_set:
            novelty = "new_mechanism"
        elif "new_technology" in change_set:
            novelty = "new_technology"
        elif {"new_script", "new_execution_step"} & change_set:
            novelty = "new_script_or_step"
        elif comparison.same_pattern and not comparison.material_change:
            novelty = "longstanding_unchanged"
        features = HeatFeatures(
            target_relevance=(
                "broad_with_older_risk"
                if relevance.elderly_relevance in {"high", "medium"}
                else "unknown"
            ),
            harm="unknown",
            spread="unknown",
            novelty=novelty,
            last_material_change_at=material_date,
            evidence_ids=[version_id],
        )
        heat = calculate_heat(features, as_of=as_of, evidence_level=gate.evidence_level)
        payload = {
            "source_version_id": version_id,
            "draft": draft,
            "gate": gate.model_dump(mode="json"),
            "heat": heat.model_dump(mode="json"),
            "comparison": comparison.model_dump(mode="json"),
            "unmapped_fields": sorted(required - mapped),
        }
        if matched:
            payload["policy_relevance_confidence"] = relevance.confidence
        try:
            if matched:
                payload["matched_pattern_id"] = matched["pattern_id"]
                payload["matched_revision_id"] = matched["revision_id"]
                receipt = self.store.submit_existing_evidence(
                    version_id=version_id,
                    holder=run_id,
                    run_id=run_id,
                    pattern_id=matched["pattern_id"],
                    base_revision_id=matched["revision_id"],
                    claim_summary=draft["one_sentence_summary"],
                    comparison=comparison.model_dump(mode="json"),
                    heat=heat.model_dump(mode="json"),
                    candidate_payload=payload,
                    reason_codes=gate.reason_codes or ["existing_pattern_evidence_review"],
                )
            else:
                receipt = self.store.submit_candidate(
                    version_id=version_id,
                    holder=run_id,
                    run_id=run_id,
                    draft=draft,
                    spans=spans,
                    heat=heat.model_dump(mode="json"),
                    candidate_payload=payload,
                    reason_codes=gate.reason_codes or ["first_publication_requires_review"],
                )
        except Exception as error:
            raise StageFailure("candidate_intake_failed") from error
        policy_input = PolicyInput(
            target_id=receipt["pattern_id"],
            candidate_hash=receipt["candidate_hash"],
            gate_version=gate.version,
            review_type="pattern_update" if matched else "new_pattern",
            gate_outcome=gate.outcome,
            evidence_level=gate.evidence_level,
            existing_public_pattern=matched is not None,
            material_change=comparison.material_change,
            public_copy_changed=matched is None,
            claims_fully_supported=receipt["missing_claim_count"] == 0,
            all_supporting_evidence_verified=True,
            named_entity_risk=False,
            legal_status_changed=False,
            evidence_level_changed=False,
            source_regression=False,
            requires_merge_or_split=False,
            relevance_confidence=relevance.confidence,
            pattern_match_confidence=comparison.confidence,
        )
        decision = evaluate_policy(self.policy, policy_input)
        try:
            self.store.record_policy(
                review_item_id=receipt["review_item_id"],
                revision_id=receipt["revision_id"],
                run_id=run_id,
                policy_version=decision.policy_version,
                policy_hash=decision.policy_hash,
                input_hash=decision.input_hash,
                gate_version=decision.gate_version,
                gate_outcome=gate.outcome.value,
                rules_outcome=decision.rules_outcome.value,
                decision_outcome=decision.outcome.value,
                execution_mode="shadow",
                reason_codes=decision.reason_codes,
                model_confidence=relevance.confidence,
                model_confidence_downgrade=decision.model_confidence_downgrade,
            )
        except Exception as error:
            raise StageFailure("policy_record_failed") from error
        try:
            self.store.finish_version(version_id, run_id, "processed")
        except Exception as error:
            raise StageFailure("version_finish_failed") from error
        return True, True

    def _complete_recovered_update(
        self, version_id: str, clean_text: str, run_id: str, receipt: dict[str, Any]
    ) -> None:
        if receipt["policy_decision_id"] is None:
            if receipt["review_status"] == "needs_evidence" and not receipt["policy_recordable"]:
                raise PendingEvidenceHold("awaiting_evidence_review")
            if receipt["review_status"] == "rejected":
                try:
                    self.store.finish_version(version_id, run_id, "processed")
                except Exception as error:
                    raise StageFailure("version_finish_failed") from error
                return
            payload = receipt["candidate_payload"]
            try:
                gate = GateDecision.model_validate(payload["gate"])
                comparison = PatternComparisonResult.model_validate(payload["comparison"])
                if (
                    not comparison.same_pattern
                    or payload["matched_pattern_id"] != receipt["pattern_id"]
                    or payload["matched_revision_id"] is None
                    or receipt["review_status"] not in {"pending", "in_review", "needs_evidence"}
                    or not receipt["policy_recordable"]
                ):
                    raise ValueError("existing_recovery_candidate_mismatch")
                confidence = payload.get("policy_relevance_confidence")
                if confidence is None:
                    relevance = self._artifact(
                        version_id, "relevance-v1", clean_text, RelevanceResult
                    )
                    if not relevance.relevant:
                        raise ValueError("existing_recovery_relevance_changed")
                    confidence = relevance.confidence
                policy_input = PolicyInput(
                    target_id=receipt["pattern_id"],
                    candidate_hash=receipt["candidate_hash"],
                    gate_version=gate.version,
                    review_type="pattern_update",
                    gate_outcome=gate.outcome,
                    evidence_level=gate.evidence_level,
                    existing_public_pattern=True,
                    material_change=comparison.material_change,
                    public_copy_changed=False,
                    claims_fully_supported=True,
                    all_supporting_evidence_verified=True,
                    named_entity_risk=False,
                    legal_status_changed=False,
                    evidence_level_changed=False,
                    source_regression=False,
                    requires_merge_or_split=False,
                    relevance_confidence=confidence,
                    pattern_match_confidence=comparison.confidence,
                )
                decision = evaluate_policy(self.policy, policy_input)
            except Exception as error:
                raise StageFailure("existing_recovery_policy_input_invalid") from error
            try:
                self.store.record_policy(
                    review_item_id=receipt["review_item_id"],
                    revision_id=receipt["revision_id"],
                    run_id=run_id,
                    policy_version=decision.policy_version,
                    policy_hash=decision.policy_hash,
                    input_hash=decision.input_hash,
                    gate_version=decision.gate_version,
                    gate_outcome=gate.outcome.value,
                    rules_outcome=decision.rules_outcome.value,
                    decision_outcome=decision.outcome.value,
                    execution_mode="shadow",
                    reason_codes=decision.reason_codes,
                    model_confidence=confidence,
                    model_confidence_downgrade=decision.model_confidence_downgrade,
                )
            except Exception as error:
                raise StageFailure("policy_record_failed") from error
        try:
            self.store.finish_version(version_id, run_id, "processed")
        except Exception as error:
            raise StageFailure("version_finish_failed") from error

    def run(
        self,
        *,
        sources: list[dict[str, Any]],
        commit_sha: str,
        registry_hash: str,
        behavior_hash: str,
    ) -> dict[str, Any]:
        run_id = self.store.start_run(
            trigger="manual",
            commit_sha=commit_sha,
            registry_hash=registry_hash,
            behavior_hash=behavior_hash,
        )
        counts: Counter[str] = Counter()
        run_error_codes: set[str] = set()
        for source in sources:
            if not source["enabled"]:
                continue
            key = source["key"]
            try:
                self.store.sync_source(source)
            except Exception:
                counts["source_failures"] += 1
                counts["source_registry_failed"] += 1
                run_error_codes.add("source_registry_failed")
                continue
            lease_key = f"source:{key}"
            try:
                acquired = self.store.acquire_lease(lease_key, run_id)
            except Exception:
                counts["source_failures"] += 1
                counts["source_lease_failed"] += 1
                run_error_codes.add("source_lease_failed")
                continue
            if not acquired:
                counts["source_lease_conflicts"] += 1
                run_error_codes.add("source_lease_conflict")
                continue
            source_failed = False
            source_deferred = False
            source_deferral_code: str | None = None
            source_error_code: str | None = None
            source_stage = "source_discovery_failed"
            cursor: str | None = None
            try:
                collector = self.collector_factory(source)
                discovered = collector.discover()[: self.max_items_per_source]
                for item in discovered:
                    if counts["discovered"] >= self.max_items:
                        break
                    counts["discovered"] += 1
                    source_stage = "source_fetch_failed"
                    normalized = collector.collect(item)
                    source_stage = "source_ingest_failed"
                    self.store.ingest(normalized)
                    cursor = item.url
                while True:
                    source_stage = "version_claim_failed"
                    claim = self.store.claim_version(key, run_id)
                    if claim is None:
                        break
                    try:
                        relevant, queued = self._process_claim(source, claim, run_id)
                        counts["relevant"] += int(relevant)
                        counts["review_items"] += int(queued)
                    except PendingEvidenceHold:
                        source_stage = "evidence_hold_deferral_failed"
                        self.store.defer_recovered_update_for_review(claim["version_id"], run_id)
                        source_deferred = True
                        source_deferral_code = "awaiting_evidence_review"
                        counts["evidence_review_deferred"] += 1
                        run_error_codes.add("awaiting_evidence_review")
                        break
                    except PendingReviewConflict as conflict:
                        source_stage = "review_deferral_failed"
                        self.store.defer_version_for_review(
                            claim["version_id"], run_id, conflict.pattern_id
                        )
                        source_deferred = True
                        source_deferral_code = "pending_review_conflict"
                        counts["pending_review_deferred"] += 1
                        run_error_codes.add("pending_review_conflict")
                        break
                    except StageFailure as failure:
                        source_failed = True
                        source_error_code = failure.code
                        run_error_codes.add(failure.code)
                        counts["analysis_failures"] += 1
                        counts[failure.code] += 1
                        self.store.finish_version(
                            claim["version_id"], run_id, "error", failure.code
                        )
                        break
                    except Exception:
                        source_failed = True
                        source_error_code = "analysis_unclassified"
                        run_error_codes.add(source_error_code)
                        counts["analysis_failures"] += 1
                        counts[source_error_code] += 1
                        self.store.finish_version(
                            claim["version_id"], run_id, "error", source_error_code
                        )
                        break
                source_stage = "source_checkpoint_failed"
                self.store.checkpoint_source(
                    key,
                    run_id,
                    success=not (source_failed or source_deferred),
                    cursor=cursor if not (source_failed or source_deferred) else None,
                    error_code=(
                        source_error_code
                        if source_failed
                        else source_deferral_code
                        if source_deferred
                        else None
                    ),
                )
            except Exception:
                source_failed = True
                source_error_code = source_stage
                run_error_codes.add(source_error_code)
                counts["source_failures"] += 1
                counts[source_error_code] += 1
                if source_stage != "source_checkpoint_failed":
                    self.store.checkpoint_source(
                        key, run_id, success=False, error_code=source_error_code
                    )
            finally:
                try:
                    self.store.release_lease(lease_key, run_id)
                except Exception:
                    counts["source_failures"] += 1
                    counts["source_lease_release_failed"] += 1
                    run_error_codes.add("source_lease_release_failed")
        outcome = (
            "degraded"
            if counts["analysis_failures"]
            or counts["source_failures"]
            or counts["pending_review_deferred"]
            or counts["evidence_review_deferred"]
            or counts["source_lease_conflicts"]
            else "success"
        )
        self.store.finish_run(
            run_id,
            outcome=outcome,
            discovered=counts["discovered"],
            relevant=counts["relevant"],
            reviews=counts["review_items"],
            error_code=(
                next(iter(run_error_codes))
                if len(run_error_codes) == 1
                else "multiple_stage_failures"
                if run_error_codes
                else None
            ),
        )
        return {"run_id": run_id, "outcome": outcome, "counts": dict(counts)}
