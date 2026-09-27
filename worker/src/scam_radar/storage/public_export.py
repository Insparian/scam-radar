"""Map an exact database v2 export to public presentation without invented copy.

Storage owns boundary mapping as well as persistence. This module never reads a
fixture, connects to a database, grants approval, or changes the SQL manifest hash.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

COMPONENT_MAXIMA = {
    "target_relevance": 30,
    "freshness": 20,
    "harm": 20,
    "spread": 15,
    "novelty": 15,
}
COPY_FIELDS = (
    "id",
    "revision_id",
    "slug",
    "risk_type",
    "legal_status",
    "evidence_level",
    "evidence_label",
    "canonical_name",
    "short_name",
    "one_sentence_summary",
    "aliases",
    "warning_signs",
    "what_to_do",
    "regions",
    "first_seen_at",
    "last_material_change_at",
    "verified_at",
    "last_verified_at",
    "evidence",
)


def text_list(value: Any, field: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(f"invalid_public_field:{field}")
    if required and not value:
        raise ValueError(f"missing_public_field:{field}")
    return value


def map_database_release(payload: dict[str, Any], expected_release_id: str) -> dict[str, Any]:
    if payload.get("schema_version") != 2 or payload.get("release_id") != expected_release_id:
        raise ValueError("release_identity_mismatch")
    result = {
        key: payload[key]
        for key in (
            "schema_version",
            "release_id",
            "release_no",
            "manifest_hash",
            "generated_at",
            "published_at",
            "as_of",
        )
    }
    patterns = []
    for raw in payload["patterns"]:
        pattern = {key: raw[key] for key in COPY_FIELDS}
        for key in COPY_FIELDS:
            if pattern[key] is None:
                raise ValueError(f"missing_public_field:{key}")
        actions = text_list(raw["what_to_do"], "what_to_do", required=True)
        hooks = text_list(raw["hooks"], "hooks", required=True)
        requested = text_list(raw["requested_actions"], "requested_actions", required=True)
        pressure = text_list(raw["pressure_tactics"], "pressure_tactics")
        money = text_list(raw["money_paths"], "money_paths")
        pattern["immediate_action"] = actions[0]
        pattern["mechanism_intro"] = "；".join(hooks)
        pattern["mechanism_steps"] = list(dict.fromkeys(pressure + requested + money))
        pattern["categories"] = [raw["pattern_type"]]
        pattern["search_terms"] = list(
            dict.fromkeys(
                [
                    raw["canonical_name"],
                    *text_list(raw["aliases"], "aliases"),
                    *hooks,
                    *requested,
                    *text_list(raw["common_phrases"], "common_phrases"),
                    *text_list(raw["contact_channels"], "contact_channels"),
                    *text_list(raw["impersonated_identities"], "impersonated_identities"),
                ]
            )
        )
        heat = raw["heat"]
        if heat["score_version"] != "scam-heat-v0.1":
            raise ValueError("unsupported_heat_version")
        components = {key: heat["breakdown"][key]["points"] for key in COMPONENT_MAXIMA}
        if (
            any(
                type(points) is not int or not 0 <= points <= COMPONENT_MAXIMA[key]
                for key, points in components.items()
            )
            or sum(components.values()) != heat["score"]
        ):
            raise ValueError("invalid_heat_components")
        age = (
            date.fromisoformat(heat["as_of"][:10])
            - datetime.fromisoformat(raw["last_material_change_at"].replace("Z", "+00:00")).date()
        ).days
        score = heat["score"]
        pattern["heat"] = {
            "score": score,
            "version": heat["score_version"],
            "as_of": heat["as_of"],
            "band": "immediate"
            if score >= 80
            else "recent"
            if score >= 65
            else "observe"
            if score >= 50
            else "database",
            "active_attention": raw["evidence_level"] in ("A", "B") and 0 <= age <= 30,
            "components": components,
        }
        # An evidence date alone does not prove a material change.
        pattern["timeline"] = [
            {"date": item["date"], "title": item["claim_summary"], "material": False}
            for item in raw["evidence"]
        ]
        patterns.append(pattern)
    result["patterns"] = patterns
    return result
