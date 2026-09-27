"""Provider protocols share prompts, schemas and budgets; no provider fallback."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, TypeVar

from jsonschema import ValidationError as SchemaError
from jsonschema import validate
from pydantic import BaseModel, ValidationError

from scam_radar.collectors.http import BoundedHttpTransport
from scam_radar.domain import ExtractionResult, PatternComparisonResult, RelevanceResult
from scam_radar.normalize.text import normalize_text

Result = TypeVar("Result", bound=BaseModel)


def _candidate_revisions(candidates: list[str] | None) -> list[dict[str, Any]]:
    revisions: list[dict[str, Any]] = []
    for value in candidates or []:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = {"revision_id": value}
        if not isinstance(parsed, dict):
            raise ValueError("invalid_pattern_candidate")
        revisions.append(parsed)
    return revisions


class HttpModelProvider:
    def __init__(
        self,
        *,
        root: Path,
        transport: BoundedHttpTransport,
        endpoint: str,
        model: str,
        protocol: Literal["openai", "gemini"],
        api_key: str = "",
        max_calls: int = 10,
        input_char_limit: int = 10000,
        before_attempt: Callable[[int, int], None] | None = None,
    ) -> None:
        if not model or not 0 <= max_calls <= 100 or not 1 <= input_char_limit <= 30000:
            raise ValueError("invalid_model_configuration")
        transport.validate_url(endpoint)
        self.root, self.transport, self.endpoint = root, transport, endpoint
        self.model, self.protocol, self.api_key = model, protocol, api_key
        self.max_calls, self.input_char_limit = max_calls, input_char_limit
        self.before_attempt = before_attempt
        self.calls = 0
        self.last_input_hash = ""
        self.last_usage: dict[str, Any] = {}

    def fingerprint(self, stage: str, text: str, candidates: list[str] | None = None) -> str:
        if len(text) > self.input_char_limit:
            raise ValueError("model_input_character_limit")
        prompt = (self.root / "prompts" / f"{stage}.md").read_text()
        schema = json.loads((self.root / "contracts/schemas" / f"{stage}.json").read_text())
        cleaned = normalize_text(text, max_chars=self.input_char_limit, defang_urls=True).text
        data = json.dumps(
            {"source_text": cleaned, "candidate_revisions": _candidate_revisions(candidates)},
            ensure_ascii=False,
        )
        return hashlib.sha256(
            json.dumps([self.model, prompt, schema, data], sort_keys=True).encode()
        ).hexdigest()

    def _run(
        self, stage: str, text: str, result_type: type[Result], candidates: list[str] | None = None
    ) -> Result:
        if len(text) > self.input_char_limit:
            raise ValueError("model_input_character_limit")
        prompt = (self.root / "prompts" / f"{stage}.md").read_text()
        schema = json.loads((self.root / "contracts/schemas" / f"{stage}.json").read_text())
        cleaned = normalize_text(text, max_chars=self.input_char_limit, defang_urls=True).text
        data = json.dumps(
            {"source_text": cleaned, "candidate_revisions": _candidate_revisions(candidates)},
            ensure_ascii=False,
        )
        self.last_input_hash = self.fingerprint(stage, text, candidates)
        for attempt in range(2):
            if self.calls >= self.max_calls:
                raise RuntimeError("model_call_budget_exhausted")
            payload: dict[str, Any]
            if self.protocol == "gemini":
                payload = {
                    "system_instruction": {"parts": [{"text": prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": data}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "responseJsonSchema": schema,
                        "maxOutputTokens": 4096,
                    },
                }
                headers = {"x-goog-api-key": self.api_key}
            else:
                payload = {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": prompt + "\n\nJSON Schema:\n" + json.dumps(schema),
                        },
                        {"role": "user", "content": data},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 4096,
                    "stream": False,
                }
                headers = {"Authorization": f"Bearer {self.api_key}"}
            headers["Content-Type"] = "application/json"
            request_body = json.dumps(payload).encode()
            if self.before_attempt is not None:
                self.before_attempt(len(request_body), 4096)
            self.calls += 1
            # Each network attempt consumes the provider cap; transient retries are
            # resumed by the durable pipeline, never hidden below this counter.
            response = self.transport.request(
                self.endpoint,
                method="POST",
                body=request_body,
                headers=headers,
                retries=0,
            )
            try:
                envelope = json.loads(response.body)
                if self.protocol == "gemini":
                    candidate = envelope["candidates"][0]
                    if candidate.get("finishReason") != "STOP":
                        raise ValueError("incomplete_model_response")
                    content = candidate["content"]["parts"][0]["text"]
                    self.last_usage = envelope.get("usageMetadata", {})
                else:
                    choice = envelope["choices"][0]
                    if choice.get("finish_reason") != "stop":
                        raise ValueError("incomplete_model_response")
                    content = choice["message"]["content"]
                    self.last_usage = envelope.get("usage", {})
                parsed = json.loads(content)
                validate(parsed, schema)
                result = result_type.model_validate(parsed)
                if isinstance(result, ExtractionResult):
                    for span in result.supporting_spans:
                        if cleaned[span.start : span.end] != span.excerpt:
                            raise ValueError("source_span_mismatch")
                return result
            except (ValueError, KeyError, IndexError, TypeError, SchemaError, ValidationError):
                if attempt == 1:
                    raise ValueError("invalid_structured_model_response") from None
        raise AssertionError("unreachable")

    def classify(self, input_id: str, text: str) -> RelevanceResult:
        del input_id
        return self._run("relevance-v1", text, RelevanceResult)

    def extract(self, input_id: str, text: str) -> ExtractionResult:
        del input_id
        return self._run("extraction-v1", text, ExtractionResult)

    def compare_patterns(
        self, input_id: str, text: str, candidate_ids: list[str]
    ) -> PatternComparisonResult:
        del input_id
        if len(candidate_ids) > 10:
            raise ValueError("candidate_limit_exceeded")
        return self._run("pattern-match-v1", text, PatternComparisonResult, candidate_ids)

    def embed(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("embeddings_disabled")
