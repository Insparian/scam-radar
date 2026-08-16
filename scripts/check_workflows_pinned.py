from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def main() -> int:
    failures: list[str] = []
    workflows = sorted((*WORKFLOW_ROOT.glob("*.yml"), *WORKFLOW_ROOT.glob("*.yaml")))
    if not workflows:
        raise RuntimeError("no GitHub Actions workflows found")
    for path in workflows:
        for use in USES.findall(path.read_text(encoding="utf-8")):
            if use.startswith(("./", "docker://")):
                continue
            if "@" not in use:
                failures.append(f"{path.relative_to(ROOT)}: action has no ref: {use}")
                continue
            action, ref = use.rsplit("@", 1)
            if not FULL_SHA.fullmatch(ref):
                failures.append(
                    f"{path.relative_to(ROOT)}: {action} must use a full 40-character commit SHA"
                )
    if failures:
        raise RuntimeError("\n".join(failures))
    print(f"workflow action pins ok: {len(workflows)} workflow files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
