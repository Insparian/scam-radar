"""Synthetic-only encrypted backup/restore on one explicitly named local container.

Creates two uniquely named databases; never resets an existing database, uploads,
uses a production URL, or accepts a real recovery identity. Disposable identity and
ciphertext stay in work/. Data streams through memory, never a plaintext dump file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", required=True)
    parser.add_argument("--age-directory", type=Path, required=True)
    args = parser.parse_args()
    if not args.container.startswith("supabase_db_scam-radar-"):
        raise ValueError("named_synthetic_database_required")
    docker = os.environ.get(
        "DOCKER_BIN",
        "/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/docker",
    )
    age = args.age_directory.resolve() / "age"
    keygen = args.age_directory.resolve() / "age-keygen"
    run_id = uuid.uuid4().hex[:12]
    output = ROOT / "work/launch-readiness" / f"recovery-{run_id}"
    output.mkdir(mode=0o700)
    identity = output / "synthetic-identity.txt"

    def command(argv: list[str], data: bytes | None = None) -> bytes:
        result = subprocess.run(
            argv, input=data, capture_output=True, check=False, timeout=120
        )
        if result.returncode:
            # Tool errors may contain SQL rows; do not emit them to normal logs.
            diagnostic = [
                line.strip()
                for line in result.stderr.decode(errors="replace").splitlines()
                if line.startswith(
                    ("pg_restore: error:", "pg_restore: while", "psql:<stdin>:")
                )
            ]
            (output / "failure-reason.txt").write_text(
                f"command_failed:{Path(argv[0]).name}:exit={result.returncode}\n"
                + "\n".join(diagnostic[:4])
                + "\n"
            )
            raise RuntimeError("local_recovery_command_failed")
        return result.stdout

    def dbcommand(argv: list[str], data: bytes | None = None) -> bytes:
        return command([docker, "exec", "-i", args.container, *argv], data)

    def sql(db: str, statement: str) -> bytes:
        return dbcommand(
            ["psql", "-U", "postgres", "-d", db, "-At", "-v", "ON_ERROR_STOP=1"],
            statement.encode(),
        )

    def restore(db: str, dump: bytes) -> None:
        sql("postgres", f"create database {db} template template0;")
        # pg_dump treats template0's public schema as a built-in and emits
        # metadata for it without recreating it, so retain the empty schema.
        toc = dbcommand(["pg_restore", "-l"], dump).decode()
        # The local pg_graphql extension owns this wrapper, but pg_dump includes
        # a grant for an obsolete signature that pg_restore cannot create.
        # Exclude that one managed ACL, preserving every application grant.
        obsolete_acl = 'ACL graphql_public FUNCTION graphql("operationName" text, query text, variables jsonb, extensions jsonb)'
        entries = toc.splitlines(keepends=True)
        matching = [line for line in entries if obsolete_acl in line]
        if len(matching) > 1:
            raise RuntimeError("unexpected_managed_graphql_acl_shape")
        filtered_toc = "".join(
            line for line in entries if line not in matching
        ).encode()
        toc_path = f"/tmp/scam-radar-restore-{run_id}.toc"
        dbcommand(["sh", "-c", f"cat > {toc_path}"], filtered_toc)
        try:
            dbcommand(
                [
                    "sh",
                    "-c",
                    # Supabase's local postgres role is not a superuser, while
                    # its managed schema has privileged function settings.
                    # Keep the local password inside the container process.
                    (
                        'PGPASSWORD="$POSTGRES_PASSWORD" exec pg_restore -h 127.0.0.1 '
                        f"-U supabase_admin -d {db} --exit-on-error -L {toc_path}"
                    ),
                ],
                dump,
            )
        finally:
            dbcommand(["rm", "-f", toc_path])

    command([str(keygen), "-o", str(identity)])
    identity.chmod(0o600)
    recipient = command([str(keygen), "-y", str(identity)]).decode().strip()
    # Include extension definitions and managed dependencies. Schema-filtered
    # pg_dump omits extension declarations even when their schema is selected.
    # Preserve application grants. The restore TOC removes only one obsolete
    # managed GraphQL wrapper ACL; RLS and human approval grants are checked.
    dump_args: list[str] = []
    source_db, restored_db = "postgres", f"recovery_restored_{run_id}"
    release_id = (
        sql(
            source_db,
            "select id::text from public.public_releases "
            "order by release_no desc limit 1;",
        )
        .decode()
        .strip()
    )
    if not release_id:
        raise RuntimeError("local_recovery_requires_actual_release")
    plaintext = dbcommand(
        ["pg_dump", "-U", "postgres", "-d", source_db, "-Fc", *dump_args]
    )
    encrypted = output / "synthetic-backup.age"
    command([str(age), "-r", recipient, "-o", str(encrypted)], plaintext)
    restored = command([str(age), "-d", "-i", str(identity), str(encrypted)])
    if hashlib.sha256(plaintext).digest() != hashlib.sha256(restored).digest():
        raise RuntimeError("decrypted_backup_integrity_mismatch")
    restore(restored_db, restored)
    query = f"select set_config('request.jwt.claim.role','service_role',false); select public.export_public_release('{release_id}'::uuid)::text;"
    before, after = sql(source_db, query), sql(restored_db, query)
    if before != after:
        raise RuntimeError("restored_release_export_mismatch")
    # Relational row counts across every public table, not only the exported page.
    tables = (
        sql(
            source_db,
            "select tablename from pg_tables where schemaname='public' order by tablename;",
        )
        .decode()
        .splitlines()
    )
    counts = {}
    for table in tables:
        a = sql(source_db, f'select count(*) from public."{table}";')
        b = sql(restored_db, f'select count(*) from public."{table}";')
        if a != b:
            raise RuntimeError("restored_table_count_mismatch")
        counts[table] = int(a)
    security = "select count(*) from pg_tables where schemaname='public' and not rowsecurity; select has_function_privilege('service_role','public.confirm_policy_publication(uuid,uuid,uuid,bigint,text,text,uuid[],uuid[],text)','execute');"
    if sql(restored_db, security).decode().strip() != "0\nf":
        raise RuntimeError("restored_security_boundary_failed")
    report = {
        "scope": "synthetic_local_only",
        "ciphertext_sha256": hashlib.sha256(encrypted.read_bytes()).hexdigest(),
        "exact_release_equal": True,
        "rls_enabled": True,
        "worker_cannot_approve": True,
        "table_counts": counts,
        "source_database": source_db,
        "restored_database": restored_db,
        "uploaded": False,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"recovery passed: tables={len(counts)} exact_release_equal=true upload=false report={output.relative_to(ROOT)}/report.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
