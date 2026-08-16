from __future__ import annotations

import json
from pathlib import Path

from run_recorded_eval import behavior_hash

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "evals" / "expected" / "behavior-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    current = behavior_hash()
    if manifest["behavior_hash"] != current:
        raise RuntimeError(
            "behavior manifest is stale; run the recorded eval, review the change, then approve a "
            "new manifest"
        )
    if manifest["launch_qualified"] is not False:
        raise RuntimeError(
            "synthetic fixture evidence must never claim launch qualification"
        )
    print(f"behavior manifest ok: {current}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
