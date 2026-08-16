from __future__ import annotations

import json

from scam_radar.domain import PipelineSummary


def render_summary(summary: PipelineSummary) -> str:
    """Structured and intentionally body-free run summary."""

    return json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
