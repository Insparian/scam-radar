from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, model_validator

from scam_radar.domain import (
    EvidenceLevel,
    GateOutcome,
    PolicyDecision,
    PolicyInput,
    PolicyOutcome,
    StrictModel,
)


class SafeToAutomateRule(StrictModel):
    review_types: tuple[Literal["pattern_update"], ...]
    evidence_levels: tuple[EvidenceLevel, ...]
    require_existing_public_pattern: bool
    require_no_material_change: bool
    require_no_public_copy_change: bool
    require_all_claims_supported: bool
    require_all_supporting_evidence_verified: bool
    deny_named_entity_risk: bool
    deny_legal_status_change: bool
    deny_evidence_level_change: bool
    deny_source_regression: bool
    deny_merge_or_split: bool


class ConfidenceDowngradeRule(StrictModel):
    enabled: bool
    minimum_relevance_confidence: float = Field(ge=0, le=1)
    minimum_pattern_match_confidence: float = Field(ge=0, le=1)


class PublicationPolicy(StrictModel):
    schema_version: Literal[1]
    policy_version: Literal["publication-policy-v0.1"]
    shadow_mode: bool
    live_auto_publish_enabled: bool
    safe_to_automate: SafeToAutomateRule
    confidence_downgrade: ConfidenceDowngradeRule
    policy_hash: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def validate_activation_mode(self) -> PublicationPolicy:
        if self.shadow_mode and self.live_auto_publish_enabled:
            raise ValueError("shadow mode cannot grant live automatic publication")
        return self


def _canonical_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def load_publication_policy(path: Path) -> PublicationPolicy:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    policy_hash = _canonical_hash(loaded)
    return PublicationPolicy.model_validate({**loaded, "policy_hash": policy_hash})


def _base_reason_codes(policy: PublicationPolicy, value: PolicyInput) -> list[str]:
    rule = policy.safe_to_automate
    reasons: list[str] = []
    if value.review_type not in rule.review_types:
        reasons.append("policy_class_requires_review")
    if value.evidence_level not in rule.evidence_levels:
        reasons.append("evidence_level_requires_review")
    if rule.require_existing_public_pattern and not value.existing_public_pattern:
        reasons.append("first_publication_requires_review")
    if rule.require_no_material_change and value.material_change:
        reasons.append("material_change_requires_review")
    if rule.require_no_public_copy_change and value.public_copy_changed:
        reasons.append("public_copy_change_requires_review")
    if rule.require_all_claims_supported and not value.claims_fully_supported:
        reasons.append("claim_support_requires_review")
    if rule.require_all_supporting_evidence_verified and not value.all_supporting_evidence_verified:
        reasons.append("evidence_verification_requires_review")
    if rule.deny_named_entity_risk and value.named_entity_risk:
        reasons.append("named_entity_risk_requires_review")
    if rule.deny_legal_status_change and value.legal_status_changed:
        reasons.append("legal_status_change_requires_review")
    if rule.deny_evidence_level_change and value.evidence_level_changed:
        reasons.append("evidence_level_change_requires_review")
    if rule.deny_source_regression and value.source_regression:
        reasons.append("source_regression_requires_review")
    if rule.deny_merge_or_split and value.requires_merge_or_split:
        reasons.append("merge_or_split_requires_review")
    return reasons


def _confidence_reason_codes(policy: PublicationPolicy, value: PolicyInput) -> list[str]:
    rule = policy.confidence_downgrade
    if not rule.enabled:
        return []
    reasons: list[str] = []
    if value.relevance_confidence is None:
        reasons.append("relevance_confidence_unknown")
    elif value.relevance_confidence < rule.minimum_relevance_confidence:
        reasons.append("relevance_confidence_low")
    if value.pattern_match_confidence is None:
        reasons.append("pattern_match_confidence_unknown")
    elif value.pattern_match_confidence < rule.minimum_pattern_match_confidence:
        reasons.append("pattern_match_confidence_low")
    return reasons


def evaluate_policy(policy: PublicationPolicy, value: PolicyInput) -> PolicyDecision:
    input_hash = _canonical_hash(value.model_dump(mode="json"))
    if value.gate_outcome != GateOutcome.ELIGIBLE:
        return PolicyDecision(
            rules_outcome=PolicyOutcome.BLOCKED,
            outcome=PolicyOutcome.BLOCKED,
            gate_version=value.gate_version,
            policy_version=policy.policy_version,
            policy_hash=policy.policy_hash,
            candidate_hash=value.candidate_hash,
            input_hash=input_hash,
            reason_codes=["evidence_gate_not_eligible"],
            model_confidence_downgrade=False,
            shadow_mode=policy.shadow_mode,
            publication_authorized=False,
        )

    base_reasons = _base_reason_codes(policy, value)
    if base_reasons:
        return PolicyDecision(
            rules_outcome=PolicyOutcome.REVIEW_REQUIRED,
            outcome=PolicyOutcome.REVIEW_REQUIRED,
            gate_version=value.gate_version,
            policy_version=policy.policy_version,
            policy_hash=policy.policy_hash,
            candidate_hash=value.candidate_hash,
            input_hash=input_hash,
            reason_codes=base_reasons,
            model_confidence_downgrade=False,
            shadow_mode=policy.shadow_mode,
            publication_authorized=False,
        )

    confidence_reasons = _confidence_reason_codes(policy, value)
    if confidence_reasons:
        return PolicyDecision(
            rules_outcome=PolicyOutcome.SAFE_TO_AUTOMATE,
            outcome=PolicyOutcome.REVIEW_REQUIRED,
            gate_version=value.gate_version,
            policy_version=policy.policy_version,
            policy_hash=policy.policy_hash,
            candidate_hash=value.candidate_hash,
            input_hash=input_hash,
            reason_codes=confidence_reasons,
            model_confidence_downgrade=True,
            shadow_mode=policy.shadow_mode,
            publication_authorized=False,
        )

    publication_authorized = policy.live_auto_publish_enabled and not policy.shadow_mode
    return PolicyDecision(
        rules_outcome=PolicyOutcome.SAFE_TO_AUTOMATE,
        outcome=PolicyOutcome.SAFE_TO_AUTOMATE,
        gate_version=value.gate_version,
        policy_version=policy.policy_version,
        policy_hash=policy.policy_hash,
        candidate_hash=value.candidate_hash,
        input_hash=input_hash,
        reason_codes=["deterministic_policy_class_matched"],
        model_confidence_downgrade=False,
        shadow_mode=policy.shadow_mode,
        publication_authorized=publication_authorized,
    )
