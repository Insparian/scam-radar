from __future__ import annotations

from scam_radar.domain import (
    AuthorityTier,
    EvidenceLevel,
    EvidenceRecord,
    GateCandidate,
    GateOutcome,
    LegalStatus,
    RiskType,
)
from scam_radar.evidence.gate import evaluate_evidence

FIELDS = {"canonical_name", "one_sentence_summary", "warning_signs", "what_to_do"}


def evidence(
    evidence_id: str,
    tier: AuthorityTier,
    claim: str,
    *,
    origin: str | None = None,
    family: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        authority_tier=tier,
        source_claim_type=claim,
        origin_group_key=origin or evidence_id,
        evidence_family_id=family or evidence_id,
        supported_fields=FIELDS,
    )


def candidate(records: list[EvidenceRecord], **overrides) -> GateCandidate:  # type: ignore[no-untyped-def]
    values = {
        "risk_type": RiskType.CONFIRMED_SCAM,
        "legal_status": LegalStatus.REPORTED_CASE,
        "evidence": records,
        "required_public_fields": FIELDS,
        "mapped_public_fields": FIELDS,
    }
    values.update(overrides)
    return GateCandidate.model_validate(values)


def test_a1_official_case_is_level_a() -> None:
    decision = evaluate_evidence(candidate([evidence("one", AuthorityTier.A1, "official_case")]))
    assert decision.version == "evidence-gate-v0.1"
    assert decision.outcome == GateOutcome.ELIGIBLE
    assert decision.evidence_level == EvidenceLevel.A
    assert decision.public_evidence_label == "警方通报的诈骗案件"


def test_a2_warning_keeps_neutral_risk_alert_wording() -> None:
    decision = evaluate_evidence(
        candidate(
            [evidence("one", AuthorityTier.A2, "regulator_warning")],
            risk_type=RiskType.RISK_ALERT,
            legal_status=LegalStatus.WARNING,
        )
    )
    assert decision.evidence_level == EvidenceLevel.A
    assert decision.public_evidence_label == "监管部门已提示风险"


def test_two_independent_media_families_are_level_b() -> None:
    decision = evaluate_evidence(
        candidate(
            [
                evidence("one", AuthorityTier.B, "media_report"),
                evidence("two", AuthorityTier.B, "media_report"),
            ]
        )
    )
    assert decision.outcome == GateOutcome.ELIGIBLE
    assert decision.evidence_level == EvidenceLevel.B


def test_copied_media_do_not_count_as_independent() -> None:
    decision = evaluate_evidence(
        candidate(
            [
                evidence("one", AuthorityTier.B, "media_report", origin="same", family="same"),
                evidence("two", AuthorityTier.B, "media_report", origin="same", family="same"),
            ]
        )
    )
    assert decision.outcome == GateOutcome.NEEDS_MORE_EVIDENCE
    assert "sources_not_independent" in decision.reason_codes


def test_missing_claim_mapping_blocks_public_eligibility() -> None:
    decision = evaluate_evidence(
        candidate(
            [evidence("one", AuthorityTier.A1, "official_case")],
            mapped_public_fields={"canonical_name"},
        )
    )
    assert decision.outcome == GateOutcome.NEEDS_MORE_EVIDENCE
    assert decision.reason_codes == ["claim_not_supported"]


def test_sensitive_data_and_legal_risk_block() -> None:
    decision = evaluate_evidence(
        candidate(
            [evidence("one", AuthorityTier.A1, "official_case")],
            contains_sensitive_data=True,
            legal_or_attribution_risk=True,
        )
    )
    assert decision.outcome == GateOutcome.BLOCKED
    assert set(decision.reason_codes) == {"sensitive_data", "legal_or_attribution_risk"}


def test_risk_alert_cannot_inherit_judgment_copy() -> None:
    decision = evaluate_evidence(
        candidate(
            [evidence("one", AuthorityTier.A1, "court_record")],
            risk_type=RiskType.RISK_ALERT,
            legal_status=LegalStatus.JUDGMENT,
        )
    )
    assert decision.outcome == GateOutcome.BLOCKED
    assert decision.evidence_level == EvidenceLevel.D


def test_duplicate_short_circuits_gate() -> None:
    decision = evaluate_evidence(candidate([], duplicate_pattern=True))
    assert decision.outcome == GateOutcome.DUPLICATE
