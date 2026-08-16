from __future__ import annotations

from typing import Any

from scam_radar.domain import ExtractionResult, PatternComparisonResult, RelevanceResult


class RecordedProvider:
    def __init__(self, records: dict[str, dict[str, Any]]) -> None:
        self._records = records
        self.calls: list[tuple[str, str]] = []

    def _stage(self, input_id: str, stage: str) -> dict[str, Any]:
        self.calls.append((stage, input_id))
        try:
            value = self._records[input_id][stage]
        except KeyError as error:
            raise KeyError(f"missing recorded {stage} result for {input_id}") from error
        if not isinstance(value, dict):
            raise TypeError(f"recorded {stage} result must be an object")
        return value

    def classify(self, input_id: str, text: str) -> RelevanceResult:
        del text
        return RelevanceResult.model_validate(self._stage(input_id, "relevance"))

    def extract(self, input_id: str, text: str) -> ExtractionResult:
        del text
        return ExtractionResult.model_validate(self._stage(input_id, "extraction"))

    def compare_patterns(
        self, input_id: str, text: str, candidate_ids: list[str]
    ) -> PatternComparisonResult:
        del text, candidate_ids
        return PatternComparisonResult.model_validate(self._stage(input_id, "pattern_match"))

    def embed(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("embeddings are disabled in V0.1")
