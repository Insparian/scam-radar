"""Red-to-green checks against a disposable copy of a real static artifact."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from check_pages_artifact import validate_pages_artifact
from check_secrets import scan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    release_id = json.loads((args.artifact / "release.json").read_text())["release_id"]
    with tempfile.TemporaryDirectory(
        prefix="negative-", dir=args.artifact.parent
    ) as temp:
        root = Path(temp) / "artifact"
        shutil.copytree(args.artifact, root)
        index = root / "search-index.json"
        original = index.read_bytes()
        changed = json.loads(original)
        changed["release_id"] = "wrong-release"
        index.write_text(json.dumps(changed))
        try:
            validate_pages_artifact(root, release_id)
        except RuntimeError as error:
            print("RED rejected: " + str(error))
        else:
            raise AssertionError("mismatched_search_accepted")
        index.write_bytes(original)
        sentinel = root / "sentinel.txt"
        sentinel.write_text("SUPABASE_SECRET_KEY")
        if not scan(root, export=True):
            raise AssertionError("secret_sentinel_accepted")
        print("RED rejected: simulated backend secret in artifact")
        sentinel.unlink()
        assert not scan(root, export=True)
        validate_pages_artifact(root, release_id)
        print("GREEN restored: artifact identity and secret checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
