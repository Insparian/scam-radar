from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[\w\u3400-\u9fff]+", re.UNICODE)


def normalize(value: str) -> str:
    return "".join(TOKEN_RE.findall(unicodedata.normalize("NFKC", value).lower()))


@dataclass(frozen=True)
class PatternDocument:
    revision_id: str
    canonical_name: str
    aliases: tuple[str, ...]
    features: tuple[str, ...]


@dataclass(frozen=True)
class CandidateMatch:
    revision_id: str
    score: int
    reason_codes: tuple[str, ...]


def retrieve_candidates(
    query_name: str,
    query_aliases: list[str],
    query_features: list[str],
    documents: list[PatternDocument],
    *,
    limit: int = 10,
) -> list[CandidateMatch]:
    names = {normalize(query_name), *(normalize(alias) for alias in query_aliases)} - {""}
    features = {normalize(value) for value in query_features} - {""}
    matches: list[CandidateMatch] = []
    for document in documents:
        document_names = {
            normalize(document.canonical_name),
            *(normalize(alias) for alias in document.aliases),
        } - {""}
        document_features = {normalize(value) for value in document.features} - {""}
        exact = names & document_names
        overlaps = features & document_features
        substring = any(
            left in right or right in left
            for left in names
            for right in document_names
            if min(len(left), len(right)) >= 3
        )
        score = min(100, len(exact) * 70 + int(substring) * 25 + len(overlaps) * 8)
        if score == 0:
            continue
        reasons: list[str] = []
        if exact:
            reasons.append("exact_name_or_alias")
        if substring:
            reasons.append("name_substring")
        if overlaps:
            reasons.append("structured_feature_overlap")
        matches.append(
            CandidateMatch(
                revision_id=document.revision_id,
                score=score,
                reason_codes=tuple(reasons),
            )
        )
    return sorted(matches, key=lambda match: (-match.score, match.revision_id))[:limit]
