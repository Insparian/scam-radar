from __future__ import annotations

import pytest

from scam_radar.evidence.hash import EvidenceHashInput, evidence_set_hash


def item(evidence_id: str) -> EvidenceHashInput:
    return EvidenceHashInput(
        evidence_id=evidence_id,
        source_version_content_hash="a" * 64,
        origin_group_key=f"origin-{evidence_id}",
        evidence_family_id=f"family-{evidence_id}",
        evidence_type="case_report",
    )


def test_hash_matches_database_serialization_and_sort_order() -> None:
    assert evidence_set_hash([item("evidence-b"), item("evidence-a")]) == (
        "8bb7e48e19ec3dd4976c8772617fe9b581a4fb0a718e1a8e9bb95eb2584554f1"
    )


def test_empty_evidence_set_matches_postgres_sha256() -> None:
    assert evidence_set_hash([]) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_duplicate_ids_and_ambiguous_delimiters_fail_closed() -> None:
    with pytest.raises(ValueError, match="unique"):
        evidence_set_hash([item("same"), item("same")])
    with pytest.raises(ValueError, match="cannot contain"):
        evidence_set_hash([item("unsafe:id")])
