from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

FALSE_VALUES = {"", "0", "false", "no", "off"}


def env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in FALSE_VALUES


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: str = "local"
    repository_root: Path
    registry_path: Path
    collect_enabled: bool = False
    ai_enabled: bool = False
    deploy_enabled: bool = False
    max_items_per_run: int = Field(default=250, ge=1, le=250)
    max_items_per_source: int = Field(default=50, ge=1, le=50)
    max_ai_calls_per_run: int = Field(default=100, ge=0, le=100)
    max_clean_text_chars: int = Field(default=50_000, ge=1_000, le=50_000)

    @model_validator(mode="after")
    def offline_environment_fails_closed(self) -> Settings:
        if self.environment in {"local", "test", "ci"} and any(
            (self.collect_enabled, self.ai_enabled, self.deploy_enabled)
        ):
            raise ValueError("external capabilities cannot be enabled in an offline environment")
        return self

    @classmethod
    def from_environment(cls, repository_root: Path | None = None) -> Settings:
        root = (repository_root or Path(__file__).resolve().parents[3]).resolve()
        registry_value = os.getenv("SOURCE_REGISTRY_PATH", "config/sources.yaml")
        registry = Path(registry_value)
        if not registry.is_absolute():
            registry = root / registry
        return cls(
            environment=os.getenv("SCAM_RADAR_ENV", "local"),
            repository_root=root,
            registry_path=registry,
            collect_enabled=env_flag("SCAM_RADAR_COLLECT_ENABLED"),
            ai_enabled=env_flag("SCAM_RADAR_AI_ENABLED"),
            deploy_enabled=env_flag("SCAM_RADAR_DEPLOY_ENABLED"),
            max_items_per_run=int(os.getenv("SCAM_RADAR_MAX_ITEMS_PER_RUN", "250")),
            max_items_per_source=int(os.getenv("SCAM_RADAR_MAX_ITEMS_PER_SOURCE", "50")),
            max_ai_calls_per_run=int(os.getenv("SCAM_RADAR_MAX_GEMINI_CALLS_PER_RUN", "100")),
            max_clean_text_chars=int(os.getenv("SCAM_RADAR_MAX_CLEAN_TEXT_CHARS", "50000")),
        )
