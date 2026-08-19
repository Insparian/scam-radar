from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthorityTier(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B = "B"
    C = "C"


class EvidenceLevel(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class RiskType(StrEnum):
    CONFIRMED_SCAM = "confirmed_scam"
    RISK_ALERT = "risk_alert"


class LegalStatus(StrEnum):
    WARNING = "warning"
    REPORTED_CASE = "reported_case"
    ENFORCEMENT = "enforcement"
    CHARGE = "charge"
    JUDGMENT = "judgment"
    UNKNOWN = "unknown"


class GateOutcome(StrEnum):
    ELIGIBLE = "eligible_for_policy"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    BLOCKED = "blocked"
    DUPLICATE = "duplicate"


class PolicyOutcome(StrEnum):
    SAFE_TO_AUTOMATE = "safe_to_automate"
    REVIEW_REQUIRED = "review_required"
    BLOCKED = "blocked"


class RelevanceResult(StrictModel):
    relevant: bool
    elderly_relevance: Literal["high", "medium", "low", "none", "unknown"]
    category: str | None
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=300)


class SupportingSpan(StrictModel):
    field_path: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    excerpt: str = Field(max_length=280)

    @model_validator(mode="after")
    def end_follows_start(self) -> SupportingSpan:
        if self.end <= self.start:
            raise ValueError("span end must follow start")
        return self


class ExtractionResult(StrictModel):
    suspected_pattern_name: str | None
    target_population: list[str]
    contact_channels: list[str]
    impersonated_identity: str | None = None
    hook: str | None
    promise: str | None
    pressure_tactics: list[str]
    requested_actions: list[str]
    money_path: str | None
    credential_requests: list[str]
    technology_used: list[str]
    regions: list[str]
    victim_count: int | None = Field(default=None, ge=0)
    reported_loss: float | None = Field(default=None, ge=0)
    individual_loss: float | None = Field(default=None, ge=0)
    case_date: date | None = None
    source_claim_type: Literal[
        "official_case", "regulator_warning", "court_record", "media_report", "unknown"
    ]
    official_status: LegalStatus
    warning_signs: list[str]
    recommended_actions: list[str]
    supporting_spans: list[SupportingSpan]


class PatternComparisonResult(StrictModel):
    same_pattern: bool
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[str]
    material_change: bool
    changes: list[str]


class NormalizedItem(StrictModel):
    source_key: str
    external_id: str | None
    canonical_url: HttpUrl
    title: str
    clean_text: str
    published_at: datetime | None = None
    author: str | None = None
    language: str | None = None
    text_truncated: bool = False
    identity_key: str
    content_hash: str


class EvidenceRecord(StrictModel):
    evidence_id: str
    authority_tier: AuthorityTier
    source_claim_type: Literal[
        "official_case", "regulator_warning", "court_record", "media_report", "unknown"
    ]
    origin_group_key: str
    evidence_family_id: str
    accessible: bool = True
    accepted: bool = True
    source_status: Literal["available", "changed", "corrected", "withdrawn", "unavailable"] = (
        "available"
    )
    supported_fields: set[str] = Field(default_factory=set)


class GateCandidate(StrictModel):
    risk_type: RiskType
    legal_status: LegalStatus
    evidence: list[EvidenceRecord]
    required_public_fields: set[str]
    mapped_public_fields: set[str]
    cluster_coherent: bool = True
    contains_sensitive_data: bool = False
    legal_or_attribution_risk: bool = False
    unsafe_detail: bool = False
    duplicate_pattern: bool = False


class GateDecision(StrictModel):
    version: Literal["evidence-gate-v0.1"] = "evidence-gate-v0.1"
    outcome: GateOutcome
    evidence_level: EvidenceLevel
    reason_codes: list[str]
    public_evidence_label: str | None


class HeatFeatures(StrictModel):
    target_relevance: Literal[
        "older_adults",
        "retirees_or_pensions",
        "broad_with_older_risk",
        "general_adults",
        "incidental_older_relevance",
        "none",
        "unknown",
    ]
    harm: Literal[
        "irreversible_or_severe",
        "major_loss_or_takeover",
        "moderate_loss",
        "data_or_grooming",
        "unknown",
    ]
    spread: Literal[
        "national_or_three_provinces",
        "two_provinces",
        "multiple_cities",
        "multiple_cases_one_region",
        "single_case",
        "unknown",
    ]
    novelty: Literal[
        "new_mechanism",
        "new_technology",
        "new_script_or_step",
        "new_packaging",
        "minor_variation",
        "longstanding_unchanged",
        "unknown",
    ]
    last_material_change_at: date | None
    evidence_ids: list[str]


class HeatSnapshot(StrictModel):
    score: int = Field(ge=0, le=100)
    band: Literal["immediate", "recent", "observe", "database"]
    active_attention: bool
    as_of: date
    version: Literal["scam-heat-v0.1"] = "scam-heat-v0.1"
    components: dict[str, int]
    feature_values: dict[str, str | None]
    evidence_ids: list[str]
    inputs_hash: str


class ReviewCandidate(StrictModel):
    target_id: str
    review_type: Literal[
        "new_pattern",
        "pattern_update",
        "merge",
        "evidence_change",
        "public_copy",
        "gate_regression",
        "source_health",
    ]
    evidence_level: EvidenceLevel
    heat_score: int
    material_date: date | None
    reason_codes: list[str]
    candidate_payload: dict[str, Any]
    candidate_hash: str
    dedupe_key: str


class PolicyInput(StrictModel):
    target_id: str
    candidate_hash: str = Field(min_length=64, max_length=64)
    gate_version: Literal["evidence-gate-v0.1"] = "evidence-gate-v0.1"
    review_type: Literal[
        "new_pattern",
        "pattern_update",
        "merge",
        "evidence_change",
        "public_copy",
        "gate_regression",
        "source_health",
    ]
    gate_outcome: GateOutcome
    evidence_level: EvidenceLevel
    existing_public_pattern: bool
    material_change: bool
    public_copy_changed: bool
    claims_fully_supported: bool
    all_supporting_evidence_verified: bool
    named_entity_risk: bool
    legal_status_changed: bool
    evidence_level_changed: bool
    source_regression: bool
    requires_merge_or_split: bool
    relevance_confidence: float | None = Field(default=None, ge=0, le=1)
    pattern_match_confidence: float | None = Field(default=None, ge=0, le=1)


class PolicyDecision(StrictModel):
    rules_outcome: PolicyOutcome
    outcome: PolicyOutcome
    gate_version: str
    policy_version: str
    policy_hash: str = Field(min_length=64, max_length=64)
    candidate_hash: str = Field(min_length=64, max_length=64)
    input_hash: str = Field(min_length=64, max_length=64)
    reason_codes: list[str] = Field(min_length=1)
    model_confidence_downgrade: bool
    shadow_mode: bool
    publication_authorized: bool

    @model_validator(mode="after")
    def authority_matches_outcome(self) -> PolicyDecision:
        if self.model_confidence_downgrade:
            if not (
                self.rules_outcome == PolicyOutcome.SAFE_TO_AUTOMATE
                and self.outcome == PolicyOutcome.REVIEW_REQUIRED
            ):
                raise ValueError(
                    "model confidence may only downgrade safe_to_automate to review_required"
                )
        elif self.outcome != self.rules_outcome:
            raise ValueError("policy outcome cannot differ without a confidence downgrade")
        if self.publication_authorized and self.outcome != PolicyOutcome.SAFE_TO_AUTOMATE:
            raise ValueError("only safe_to_automate may grant publication authority")
        if self.publication_authorized and self.shadow_mode:
            raise ValueError("shadow decisions cannot grant publication authority")
        return self


class PipelineSummary(StrictModel):
    run_id: str
    discovered: int = 0
    normalized: int = 0
    exact_duplicates: int = 0
    relevant: int = 0
    irrelevant: int = 0
    review_items: int = 0
    eligible: int = 0
    blocked: int = 0
    policy_safe_to_automate: int = 0
    policy_review_required: int = 0
    policy_blocked: int = 0
    shadow_auto_candidates: int = 0
    auto_publication_authorized: int = 0
    output_release_id: str | None = None
    reason_counts: dict[str, int] = Field(default_factory=dict)
