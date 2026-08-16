from __future__ import annotations

from scam_radar.domain import (
    AuthorityTier,
    EvidenceLevel,
    GateCandidate,
    GateDecision,
    GateOutcome,
    LegalStatus,
    RiskType,
)


def _accepted_available(candidate: GateCandidate):  # type: ignore[no-untyped-def]
    return [
        evidence
        for evidence in candidate.evidence
        if evidence.accepted and evidence.accessible and evidence.source_status == "available"
    ]


def _public_label(candidate: GateCandidate, level: EvidenceLevel) -> str | None:
    if level == EvidenceLevel.A:
        if candidate.risk_type == RiskType.RISK_ALERT:
            return "监管部门已提示风险"
        return {
            LegalStatus.JUDGMENT: "司法机关已公开裁判",
            LegalStatus.ENFORCEMENT: "执法机关已公开处置",
            LegalStatus.CHARGE: "司法机关已公开指控",
            LegalStatus.REPORTED_CASE: "警方通报的诈骗案件",
            LegalStatus.WARNING: "权威机构已发布风险提示",
            LegalStatus.UNKNOWN: "权威来源已公开相关信息",
        }[candidate.legal_status]
    if level == EvidenceLevel.B:
        return "多家可信来源报道了相似做法"
    return None


def evaluate_evidence(candidate: GateCandidate) -> GateDecision:
    if candidate.duplicate_pattern:
        return GateDecision(
            outcome=GateOutcome.DUPLICATE,
            evidence_level=EvidenceLevel.D,
            reason_codes=["duplicate_pattern"],
            public_evidence_label=None,
        )
    blockers: list[str] = []
    if not candidate.cluster_coherent:
        blockers.append("cluster_incoherent")
    if candidate.contains_sensitive_data:
        blockers.append("sensitive_data")
    if candidate.legal_or_attribution_risk:
        blockers.append("legal_or_attribution_risk")
    if candidate.unsafe_detail:
        blockers.append("unsafe_detail")
    if blockers:
        return GateDecision(
            outcome=GateOutcome.BLOCKED,
            evidence_level=EvidenceLevel.D,
            reason_codes=blockers,
            public_evidence_label=None,
        )

    evidence = _accepted_available(candidate)
    if not evidence:
        return GateDecision(
            outcome=GateOutcome.NEEDS_MORE_EVIDENCE,
            evidence_level=EvidenceLevel.C,
            reason_codes=["source_unavailable", "insufficient_evidence"],
            public_evidence_label=None,
        )

    official = any(
        item.authority_tier == AuthorityTier.A1
        and item.source_claim_type in {"official_case", "court_record"}
        for item in evidence
    ) or any(
        item.authority_tier == AuthorityTier.A2 and item.source_claim_type == "regulator_warning"
        for item in evidence
    )
    families = {item.evidence_family_id for item in evidence}
    origins = {item.origin_group_key for item in evidence}
    corroborated = (
        len(families) >= 2
        and len(origins) >= 2
        and all(item.authority_tier != AuthorityTier.C for item in evidence)
    )

    if official:
        level = EvidenceLevel.A
    elif corroborated:
        level = EvidenceLevel.B
    else:
        level = EvidenceLevel.C

    reasons: list[str] = []
    missing_fields = candidate.required_public_fields - candidate.mapped_public_fields
    if missing_fields:
        reasons.append("claim_not_supported")
    if level == EvidenceLevel.C:
        reasons.append("insufficient_evidence")
        if len(evidence) > 1 and not corroborated:
            reasons.append("sources_not_independent")

    if candidate.risk_type == RiskType.RISK_ALERT and candidate.legal_status in {
        LegalStatus.CHARGE,
        LegalStatus.JUDGMENT,
    }:
        reasons.append("legal_or_attribution_risk")
        return GateDecision(
            outcome=GateOutcome.BLOCKED,
            evidence_level=EvidenceLevel.D,
            reason_codes=reasons,
            public_evidence_label=None,
        )

    if reasons:
        return GateDecision(
            outcome=GateOutcome.NEEDS_MORE_EVIDENCE,
            evidence_level=level,
            reason_codes=reasons,
            public_evidence_label=None,
        )

    return GateDecision(
        outcome=GateOutcome.ELIGIBLE,
        evidence_level=level,
        reason_codes=[],
        public_evidence_label=_public_label(candidate, level),
    )
