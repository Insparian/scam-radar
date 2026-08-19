from __future__ import annotations

import json
from pathlib import Path

from scam_radar.pipeline import FixturePipeline
from scam_radar.storage.memory import MemoryStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    output = ROOT / "work" / "release"
    store = MemoryStore()
    first = FixturePipeline(ROOT, store).run(output)
    second = FixturePipeline(ROOT, store).run(output)
    if (
        first.eligible != 5
        or first.policy_review_required != 4
        or first.policy_safe_to_automate != 1
        or first.review_items != 5
    ):
        raise RuntimeError(
            "fixture demo did not route four exceptions and one shadow-safe confirmation"
        )
    if first.shadow_auto_candidates != 1 or first.auto_publication_authorized != 0:
        raise RuntimeError("fixture demo unexpectedly granted automatic publication")
    if second.exact_duplicates != 5 or second.review_items != 0:
        raise RuntimeError("fixture demo is not idempotent")
    release_path = output / str(first.output_release_id) / "public-release.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    if (
        release["release_id"] != first.output_release_id
        or len(release["patterns"]) != 5
    ):
        raise RuntimeError("fixture release is incomplete")
    print(
        json.dumps(
            {
                "status": "ok",
                "release_id": first.output_release_id,
                "patterns": len(release["patterns"]),
                "review_items": first.review_items,
                "policy_review_required": first.policy_review_required,
                "policy_safe_to_automate": first.policy_safe_to_automate,
                "shadow_auto_candidates": first.shadow_auto_candidates,
                "auto_publication_authorized": first.auto_publication_authorized,
                "idempotent_duplicates_on_rerun": second.exact_duplicates,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
