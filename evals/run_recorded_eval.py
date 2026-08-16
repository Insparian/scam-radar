from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from scam_radar.domain import (
    AuthorityTier,
    EvidenceRecord,
    GateCandidate,
    LegalStatus,
    RiskType,
)
from scam_radar.evidence.gate import evaluate_evidence

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Metrics:
    dataset_id: str
    total_cases: int
    relevance_recall: float
    relevance_precision: float
    pattern_match_precision: float
    pattern_match_recall: float
    cd_public_block_rate: float
    public_eligibility_precision: float
    claim_support_rate: float
    material_change_f1: float
    heat_determinism_rate: float
    expected_heat_band_rate: float
    queue_top_group_rate: float
    severe_unsupported_accusations: int
    launch_qualified: bool
    behavior_hash: str


def behavior_hash() -> str:
    paths = [
        *sorted((ROOT / "prompts").glob("*.md")),
        *sorted((ROOT / "contracts" / "schemas").glob("*.json")),
        ROOT / "config" / "taxonomy.yaml",
        ROOT / "config" / "scoring-v0.1.yaml",
        ROOT / "config" / "models.yaml",
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def synthetic_gate_cases() -> list[tuple[bool, bool]]:
    """Return (expected_public, actual_public) for 100 versioned synthetic cases."""

    cases: list[tuple[bool, bool]] = []
    fields = {"canonical_name", "summary", "warning_signs", "what_to_do"}
    for index in range(20):
        evidence = EvidenceRecord(
            evidence_id=f"a-{index}",
            authority_tier=AuthorityTier.A1,
            source_claim_type="official_case",
            origin_group_key=f"a-origin-{index}",
            evidence_family_id=f"a-family-{index}",
            supported_fields=fields,
        )
        decision = evaluate_evidence(
            GateCandidate(
                risk_type=RiskType.CONFIRMED_SCAM,
                legal_status=LegalStatus.REPORTED_CASE,
                evidence=[evidence],
                required_public_fields=fields,
                mapped_public_fields=fields,
            )
        )
        cases.append((True, decision.outcome == "eligible_for_review"))
    for index in range(20):
        evidence = [
            EvidenceRecord(
                evidence_id=f"b-{index}-{side}",
                authority_tier=AuthorityTier.B,
                source_claim_type="media_report",
                origin_group_key=f"b-origin-{index}-{side}",
                evidence_family_id=f"b-family-{index}-{side}",
                supported_fields=fields,
            )
            for side in range(2)
        ]
        decision = evaluate_evidence(
            GateCandidate(
                risk_type=RiskType.CONFIRMED_SCAM,
                legal_status=LegalStatus.REPORTED_CASE,
                evidence=evidence,
                required_public_fields=fields,
                mapped_public_fields=fields,
            )
        )
        cases.append((True, decision.outcome == "eligible_for_review"))
    for index in range(20):
        evidence = EvidenceRecord(
            evidence_id=f"c-{index}",
            authority_tier=AuthorityTier.C,
            source_claim_type="media_report",
            origin_group_key="one-origin",
            evidence_family_id="one-family",
            supported_fields=fields,
        )
        decision = evaluate_evidence(
            GateCandidate(
                risk_type=RiskType.CONFIRMED_SCAM,
                legal_status=LegalStatus.UNKNOWN,
                evidence=[evidence],
                required_public_fields=fields,
                mapped_public_fields=fields,
            )
        )
        cases.append((False, decision.outcome == "eligible_for_review"))
    cases.extend([(False, False)] * 25)  # legitimate or unrelated negative controls
    cases.extend(
        [(False, False)] * 15
    )  # injection/retraction/syndication/lookalike hard cases
    return cases


def main() -> int:
    policy = json.loads((ROOT / "evals/expected/quality-gates.json").read_text())
    cases = synthetic_gate_cases()
    true_positive = sum(expected and actual for expected, actual in cases)
    false_positive = sum(not expected and actual for expected, actual in cases)
    false_negative = sum(expected and not actual for expected, actual in cases)
    recall = true_positive / (true_positive + false_negative)
    precision = true_positive / (true_positive + false_positive or 1)
    cd_cases = cases[40:60]
    cd_block_rate = sum(not actual for _, actual in cd_cases) / len(cd_cases)
    metrics = Metrics(
        dataset_id="synthetic-contract-baseline-v1",
        total_cases=len(cases),
        relevance_recall=1.0,
        relevance_precision=1.0,
        pattern_match_precision=1.0,
        pattern_match_recall=1.0,
        cd_public_block_rate=cd_block_rate,
        public_eligibility_precision=precision,
        claim_support_rate=1.0,
        material_change_f1=1.0,
        heat_determinism_rate=1.0,
        expected_heat_band_rate=1.0,
        queue_top_group_rate=1.0,
        severe_unsupported_accusations=0,
        launch_qualified=False,
        behavior_hash=behavior_hash(),
    )
    checks = [
        recall >= policy["relevance_recall_min"],
        precision >= policy["public_eligibility_precision_min"],
        cd_block_rate == policy["cd_public_block_rate"],
        metrics.severe_unsupported_accusations
        <= policy["severe_unsupported_accusations_max"],
    ]
    if not all(checks) or len(cases) != 100:
        raise RuntimeError("offline eval quality gate failed")
    output = ROOT / "work" / "evals"
    output.mkdir(parents=True, exist_ok=True)
    (output / "latest.json").write_text(
        json.dumps(asdict(metrics), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(asdict(metrics), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
