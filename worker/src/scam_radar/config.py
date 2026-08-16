from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker


@dataclass(frozen=True)
class Registry:
    data: dict[str, Any]
    content_hash: str

    @property
    def sources(self) -> list[dict[str, Any]]:
        sources = self.data["sources"]
        if not isinstance(sources, list):
            raise TypeError("validated sources must be a list")
        return sources


def _load_mapping(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    return loaded


def load_registry(registry_path: Path, schema_path: Path, repository_root: Path) -> Registry:
    data = _load_mapping(registry_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        rendered = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"source registry schema validation failed: {rendered}")

    keys = [source["key"] for source in data["sources"]]
    if len(keys) != len(set(keys)):
        raise ValueError("source registry contains duplicate source keys")

    for source in data["sources"]:
        entry_url = source["collector"]["entry_url"]
        if urlparse(entry_url).scheme != "https":
            raise ValueError(f"{source['key']}: entry_url must use https")
        fixture = (repository_root / source["parser"]["fixture"]).resolve()
        if repository_root not in fixture.parents or not fixture.is_file():
            raise ValueError(f"{source['key']}: fixture is missing or outside the repository")
        if source["enabled"] and not (
            source["policy"]["collection_allowed"] and source["policy"]["reviewed_at"]
        ):
            raise ValueError(
                f"{source['key']}: enabled source lacks reviewed collection permission"
            )
        if source["authority_tier"] == "C" and source["enabled"]:
            raise ValueError(f"{source['key']}: Tier C cannot be enabled in V0.1")

    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return Registry(data=data, content_hash=hashlib.sha256(canonical.encode()).hexdigest())
