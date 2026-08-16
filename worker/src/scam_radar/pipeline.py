from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import HttpUrl

from scam_radar.dedup.service import content_hash, identity_key
from scam_radar.domain import (
    AuthorityTier,
    EvidenceLevel,
    EvidenceRecord,
    GateCandidate,
    GateOutcome,
    HeatFeatures,
    LegalStatus,
    NormalizedItem,
    PipelineSummary,
    RiskType,
)
from scam_radar.evidence.gate import evaluate_evidence
from scam_radar.llm.recorded import RecordedProvider
from scam_radar.normalize.text import normalize_text
from scam_radar.review.queue import make_review_candidate
from scam_radar.scoring.heat import calculate_heat
from scam_radar.storage.memory import MemoryStore

REQUIRED_PUBLIC_FIELDS = {
    "canonical_name",
    "one_sentence_summary",
    "mechanism_steps",
    "warning_signs",
    "what_to_do",
    "evidence",
    "last_material_change_at",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def build_search_index(release: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "release_id": release["release_id"],
        "items": [
            {
                "slug": pattern["slug"],
                "canonical_name": pattern["canonical_name"],
                "aliases": pattern["aliases"],
                "keywords": pattern["search_terms"],
            }
            for pattern in release["patterns"]
        ],
    }


class FixturePipeline:
    def __init__(self, repository_root: Path, store: MemoryStore | None = None) -> None:
        self.root = repository_root
        self.store = store or MemoryStore()
        fixture_root = repository_root / "evals" / "fixtures"
        self.release = load_json(fixture_root / "public-release" / "public-release.json")
        self.recorded = load_json(fixture_root / "recorded-ai.json")
        self.pipeline_input = load_json(fixture_root / "pipeline-input.json")
        self.provider = RecordedProvider(self.recorded)

    def _normalized_item(self, pattern: dict[str, Any]) -> NormalizedItem:
        text = "\n".join(
            [
                pattern["one_sentence_summary"],
                *pattern["mechanism_steps"],
                *pattern["warning_signs"],
            ]
        )
        cleaned = normalize_text(text)
        url = f"https://fixture.example.invalid/reports/{pattern['slug']}"
        return NormalizedItem(
            source_key="fixture-authority",
            external_id=pattern["slug"],
            canonical_url=HttpUrl(url),
            title=pattern["canonical_name"],
            clean_text=cleaned.text,
            language="zh-CN",
            text_truncated=cleaned.truncated,
            identity_key=identity_key(url, pattern["slug"]),
            content_hash=content_hash(pattern["canonical_name"], cleaned.text),
        )

    def _evidence(self, pattern: dict[str, Any]) -> list[EvidenceRecord]:
        source_claim_type = self.pipeline_input[pattern["slug"]]["source_claim_type"]
        records: list[EvidenceRecord] = []
        for index, item in enumerate(pattern["evidence"]):
            records.append(
                EvidenceRecord(
                    evidence_id=f"{pattern['slug']}-evidence-{index + 1}",
                    authority_tier=AuthorityTier(item["authority_tier"]),
                    source_claim_type=source_claim_type,
                    origin_group_key=f"{pattern['slug']}-origin-{index + 1}",
                    evidence_family_id=f"{pattern['slug']}-family-{index + 1}",
                    supported_fields=REQUIRED_PUBLIC_FIELDS,
                )
            )
        return records

    def run(self, output_root: Path) -> PipelineSummary:
        counts: Counter[str] = Counter()
        patterns: list[dict[str, Any]] = []
        run_id = f"fixture-{uuid.uuid4()}"
        for pattern in self.release["patterns"]:
            counts["discovered"] += 1
            item = self._normalized_item(pattern)
            if not self.store.upsert_item(item):
                counts["exact_duplicates"] += 1
                continue
            counts["normalized"] += 1
            relevance = self.provider.classify(pattern["slug"], item.clean_text)
            if not relevance.relevant:
                counts["irrelevant"] += 1
                continue
            counts["relevant"] += 1
            extraction = self.provider.extract(pattern["slug"], item.clean_text)
            comparison = self.provider.compare_patterns(pattern["slug"], item.clean_text, [])
            evidence = self._evidence(pattern)
            candidate = GateCandidate(
                risk_type=RiskType(pattern["risk_type"]),
                legal_status=LegalStatus(pattern["legal_status"]),
                evidence=evidence,
                required_public_fields=REQUIRED_PUBLIC_FIELDS,
                mapped_public_fields=REQUIRED_PUBLIC_FIELDS,
            )
            gate = evaluate_evidence(candidate)
            for reason in gate.reason_codes:
                counts[f"reason:{reason}"] += 1
            if gate.outcome != GateOutcome.ELIGIBLE:
                counts["blocked"] += 1
                continue
            counts["eligible"] += 1
            fixture_features = self.pipeline_input[pattern["slug"]]
            features = HeatFeatures(
                target_relevance=fixture_features["target_relevance"],
                harm=fixture_features["harm"],
                spread=fixture_features["spread"],
                novelty=fixture_features["novelty"],
                last_material_change_at=date.fromisoformat(pattern["last_material_change_at"]),
                evidence_ids=[record.evidence_id for record in evidence],
            )
            heat = calculate_heat(
                features,
                as_of=date.fromisoformat(self.release["as_of"]),
                evidence_level=EvidenceLevel(pattern["evidence_level"]),
            )
            if heat.score != pattern["heat"]["score"]:
                message = (
                    f"fixture heat drift for {pattern['slug']}: "
                    f"{heat.score} != {pattern['heat']['score']}"
                )
                raise ValueError(message)
            review = make_review_candidate(
                target_id=pattern["id"],
                review_type="new_pattern",
                evidence_level=gate.evidence_level,
                heat_score=heat.score,
                material_date=features.last_material_change_at,
                reason_codes=comparison.reason_codes,
                payload={
                    "canonical_name": pattern["canonical_name"],
                    "extraction": extraction.model_dump(mode="json"),
                    "gate": gate.model_dump(mode="json"),
                    "heat": heat.model_dump(mode="json"),
                },
            )
            if self.store.upsert_review(review):
                counts["review_items"] += 1
            patterns.append(pattern)

        output_release = {**self.release, "patterns": patterns or self.release["patterns"]}
        release_root = output_root / self.release["release_id"]
        release_root.mkdir(parents=True, exist_ok=True)
        (release_root / "public-release.json").write_text(
            json.dumps(output_release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (release_root / "search-index.json").write_text(
            json.dumps(build_search_index(output_release), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (release_root / "release.json").write_text(
            json.dumps(
                {
                    "release_id": self.release["release_id"],
                    "schema_version": self.release["schema_version"],
                    "pattern_count": len(output_release["patterns"]),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return PipelineSummary(
            run_id=run_id,
            discovered=counts["discovered"],
            normalized=counts["normalized"],
            exact_duplicates=counts["exact_duplicates"],
            relevant=counts["relevant"],
            irrelevant=counts["irrelevant"],
            review_items=counts["review_items"],
            eligible=counts["eligible"],
            blocked=counts["blocked"],
            output_release_id=self.release["release_id"],
            reason_counts={
                key.removeprefix("reason:"): value
                for key, value in counts.items()
                if key.startswith("reason:")
            },
        )
