from __future__ import annotations

from typing import Protocol

from scam_radar.domain import ExtractionResult, PatternComparisonResult, RelevanceResult


class ActivationRequired(RuntimeError):
    pass


class LLMProvider(Protocol):
    def classify(self, input_id: str, text: str) -> RelevanceResult: ...

    def extract(self, input_id: str, text: str) -> ExtractionResult: ...

    def compare_patterns(
        self, input_id: str, text: str, candidate_ids: list[str]
    ) -> PatternComparisonResult: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class GeminiProvider:
    """Activation boundary; the network transport is deliberately not present offline."""

    def __init__(self, *, enabled: bool = False) -> None:
        if enabled:
            raise ActivationRequired(
                "Gemini transport requires the external-activation data-flow approval"
            )

    def _disabled(self) -> ActivationRequired:
        return ActivationRequired("Gemini is disabled; use RecordedProvider offline")

    def classify(self, input_id: str, text: str) -> RelevanceResult:
        del input_id, text
        raise self._disabled()

    def extract(self, input_id: str, text: str) -> ExtractionResult:
        del input_id, text
        raise self._disabled()

    def compare_patterns(
        self, input_id: str, text: str, candidate_ids: list[str]
    ) -> PatternComparisonResult:
        del input_id, text, candidate_ids
        raise self._disabled()

    def embed(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise self._disabled()
