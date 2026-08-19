from __future__ import annotations

import json

from scam_radar.pipeline import FixturePipeline
from scam_radar.storage.memory import MemoryStore


def test_fixture_pipeline_is_complete_and_idempotent(repository_root, tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = MemoryStore()
    first = FixturePipeline(repository_root, store).run(tmp_path)
    second = FixturePipeline(repository_root, store).run(tmp_path)
    assert first.discovered == 5
    assert first.eligible == 5
    assert first.review_items == 5
    assert first.policy_safe_to_automate == 1
    assert first.policy_review_required == 4
    assert first.shadow_auto_candidates == 1
    assert first.auto_publication_authorized == 0
    assert second.exact_duplicates == 5
    assert second.review_items == 0
    assert second.policy_review_required == 0
    assert second.policy_safe_to_automate == 0
    release_root = tmp_path / str(first.output_release_id)
    release = json.loads((release_root / "public-release.json").read_text())
    search = json.loads((release_root / "search-index.json").read_text())
    metadata = json.loads((release_root / "release.json").read_text())
    assert len(release["patterns"]) == 5
    assert release["release_id"] == search["release_id"] == metadata["release_id"]
