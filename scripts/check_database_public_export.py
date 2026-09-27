"""Exercise the real SQL review/release contract and its public presentation map."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker/src"))
from scam_radar.storage.public_export import map_database_release


def main() -> int:
    docker = (
        os.getenv("DOCKER_BIN")
        or shutil.which("docker")
        or "/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/docker"
    )
    container = os.getenv("SUPABASE_DB_CONTAINER", "supabase_db_scam-radar-offline")
    # The existing contract authenticates the synthetic reviewer, approves through
    # RPC, freezes the release, checks immutability, and rolls its transaction back.
    sql = (ROOT / "supabase/tests/local_policy_contract.sql").read_text()
    sql = sql.replace(
        "\nrollback;\n",
        "\nselect 'PUBLIC_EXPORT=' || public.export_public_release(release_id)::text from local_contract_context;\nrollback;\n",
    )
    sql = sql.replace(
        "\nrollback;\n",
        "\n"
        + (ROOT / "supabase/tests/local_deployment_contract.sql").read_text()
        + "\nrollback;\n",
    )
    run = subprocess.run(
        [
            docker,
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=sql,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if run.returncode:
        raise RuntimeError("local_database_export_contract_failed")
    exports = [
        line.removeprefix("PUBLIC_EXPORT=")
        for line in run.stdout.splitlines()
        if line.startswith("PUBLIC_EXPORT=")
    ]
    if len(exports) != 1:
        raise RuntimeError("expected_one_database_export")
    print("real deployment lifecycle RPC checks passed")
    raw = json.loads(exports[0])
    mapped = map_database_release(raw, raw["release_id"])
    out = ROOT / "work/launch-readiness"
    out.mkdir(parents=True, exist_ok=True)
    target = out / "database-public-release.json"
    target.write_text(json.dumps(mapped, ensure_ascii=False, indent=2) + "\n")
    subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "import {readFileSync} from 'node:fs'; import {assertRelease} from './web/lib/public-data/validate.ts'; assertRelease(JSON.parse(readFileSync(process.argv[1], 'utf8')));",
            str(target),
        ],
        cwd=ROOT,
        check=True,
    )
    print(f"database public mapping passed: patterns={len(mapped['patterns'])}")
    for label, mutate in [
        ("release_mismatch", lambda p: p.update(release_id="different-release")),
        ("missing_actions", lambda p: p["patterns"][0].pop("what_to_do")),
        ("missing_mechanism", lambda p: p["patterns"][0].update(hooks=[])),
        ("invalid_heat", lambda p: p["patterns"][0]["heat"].update(score=101)),
    ]:
        damaged = json.loads(exports[0])
        mutate(damaged)
        try:
            map_database_release(damaged, raw["release_id"])
        except (ValueError, KeyError):
            print(f"RED rejected: {label}")
        else:
            raise AssertionError(f"invalid export accepted: {label}")
    print("GREEN restored: exact database export accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
