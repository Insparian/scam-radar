from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections.abc import Mapping

BOOTSTRAP_REVIEWER_SQL = """
with upserted_reviewer as (
    insert into public.admin_users (user_id, role, enabled)
    select id, 'reviewer', true
    from auth.users
    where lower(email) = lower(:'reviewer_email')
    on conflict (user_id) do update
    set role = 'reviewer', enabled = true
    returning user_id
)
select count(*)
from upserted_reviewer;
"""

FOUNDATION_QUERY = """
select json_build_object(
    'migrations_ok', (
        select array_agg(version order by version) = array[
            '20260816000100',
            '20260816000200',
            '20260816000300',
            '20260816000400',
            '20260916000100'
        ]::text[]
        from supabase_migrations.schema_migrations
        where version in (
            '20260816000100',
            '20260816000200',
            '20260816000300',
            '20260816000400',
            '20260916000100'
        )
    ),
    'one_reviewer', (
        select count(*) = 1
        from public.admin_users
        where enabled and role = 'reviewer'
    ),
    'empty_application_data', not exists (
        select 1 from public.source_items
        union all select 1 from public.ai_artifacts
        union all select 1 from public.scam_patterns
        union all select 1 from public.pattern_evidence
        union all select 1 from public.policy_decisions
        union all select 1 from public.public_releases
    ),
    'anon_has_no_tables', not exists (
        select 1
        from information_schema.role_table_grants
        where grantee = 'anon' and table_schema = 'public'
    ),
    'authenticated_has_no_tables', not exists (
        select 1
        from information_schema.role_table_grants
        where grantee = 'authenticated' and table_schema = 'public'
    ),
    'service_role_has_no_tables', not exists (
        select 1
        from information_schema.role_table_grants
        where grantee = 'service_role' and table_schema = 'public'
    ),
    'reviewer_rpc_only_authenticated',
        has_function_privilege(
            'authenticated',
            'public.confirm_policy_publication(uuid,uuid,uuid,bigint,text,text,uuid[],uuid[],text)',
            'EXECUTE'
        )
        and not has_function_privilege(
            'anon',
            'public.confirm_policy_publication(uuid,uuid,uuid,bigint,text,text,uuid[],uuid[],text)',
            'EXECUTE'
        )
        and not has_function_privilege(
            'service_role',
            'public.confirm_policy_publication(uuid,uuid,uuid,bigint,text,text,uuid[],uuid[],text)',
            'EXECUTE'
        ),
    'worker_rpc_only_service_role',
        has_function_privilege(
            'service_role',
            'public.record_policy_decision(uuid,uuid,text,text,text,text,text,text,text,text,text,boolean,boolean,text[],uuid,numeric)',
            'EXECUTE'
        )
        and not has_function_privilege(
            'authenticated',
            'public.record_policy_decision(uuid,uuid,text,text,text,text,text,text,text,text,text,boolean,boolean,text[],uuid,numeric)',
            'EXECUTE'
        ),
    'exporter_rpc_only_service_role',
        has_function_privilege(
            'service_role',
            'public.export_public_release(uuid)',
            'EXECUTE'
        )
        and not has_function_privilege(
            'anon',
            'public.export_public_release(uuid)',
            'EXECUTE'
        )
        and not has_function_privilege(
            'authenticated',
            'public.export_public_release(uuid)',
            'EXECUTE'
    ),
    'live_policy_allowlist_empty', not exists (
        select 1 from private.active_live_publication_policies()
    )
)::text;
"""


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"required protected environment value is missing: {name}")
    return value


def run_psql(
    db_url: str,
    sql: str,
    *,
    variables: Mapping[str, str] | None = None,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        "psql",
        db_url,
        "--no-psqlrc",
        "--no-align",
        "--tuples-only",
        "--set=ON_ERROR_STOP=1",
    ]
    for name, value in (variables or {}).items():
        command.append(f"--set={name}={value}")
    result = subprocess.run(
        command,
        check=False,
        input=sql,
        text=True,
        capture_output=True,
        timeout=60,
        env={**os.environ, "PGAPPNAME": "scam-radar-foundation"},
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError("production database command failed; output was withheld")
    if not expect_success and result.returncode == 0:
        raise RuntimeError("production database unexpectedly granted forbidden access")
    return result


def bootstrap_reviewer() -> None:
    reviewer_email = required_env("SUPABASE_REVIEWER_EMAIL")
    db_url = required_env("SUPABASE_DB_URL")
    if "@" not in reviewer_email or reviewer_email.endswith(".invalid"):
        raise RuntimeError("protected reviewer mailbox is invalid")
    result = run_psql(
        db_url,
        BOOTSTRAP_REVIEWER_SQL,
        variables={"reviewer_email": reviewer_email},
    )
    reviewer_counts = [
        line.strip() for line in result.stdout.splitlines() if line.strip()
    ]
    if reviewer_counts != ["1"]:
        raise RuntimeError(
            "reviewer bootstrap requires exactly one pre-created Supabase Auth user"
        )
    print("reviewer bootstrap ok: auth_user=existing admin_mapping=enabled")


def parse_single_json_row(
    result: subprocess.CompletedProcess[str],
) -> dict[str, object]:
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(rows) != 1:
        raise RuntimeError(
            "production foundation query returned an unexpected row count"
        )
    payload = json.loads(rows[0])
    if not isinstance(payload, dict):
        raise TypeError("production foundation query returned an unexpected shape")
    return payload


def verify_foundation() -> None:
    db_url = required_env("SUPABASE_DB_URL")
    result = run_psql(
        db_url,
        FOUNDATION_QUERY,
        variables=None,
    )
    payload = parse_single_json_row(result)
    failures = sorted(key for key, value in payload.items() if value is not True)
    if failures:
        raise RuntimeError(
            "production foundation contract failed: " + ", ".join(failures)
        )

    denied_probes = {
        "anon_table": "set role anon; select user_id from public.admin_users limit 1;",
        "authenticated_table": (
            "set role authenticated; select user_id from public.admin_users limit 1;"
        ),
        "service_role_table": (
            "set role service_role; select user_id from public.admin_users limit 1;"
        ),
        "service_role_human_rpc": (
            "set role service_role; "
            "select public.confirm_policy_publication("
            "null,null,null,null,null,null,null,null,null);"
        ),
    }
    for probe in denied_probes.values():
        run_psql(db_url, probe, expect_success=False)

    reviewer_guard = run_psql(
        db_url,
        "set role authenticated; "
        "select public.confirm_policy_publication("
        "null,null,null,null,null,null,null,null,null);",
        expect_success=False,
    )
    if not any(
        marker in reviewer_guard.stderr
        for marker in (
            "authenticated_reviewer_role_required",
            "reviewer_identity_required",
        )
    ):
        raise RuntimeError(
            "authenticated reviewer RPC did not fail at its identity guard"
        )

    exporter_guard = run_psql(
        db_url,
        "begin; set local role service_role; "
        "select set_config('request.jwt.claim.role','service_role',true); "
        "select public.export_public_release("
        "'00000000-0000-0000-0000-000000000000'::uuid); rollback;",
        expect_success=False,
    )
    if "release_not_exportable" not in exporter_guard.stderr:
        raise RuntimeError("exporter RPC did not reach its immutable-release guard")

    print(
        "production Supabase foundation ok: migrations=5 reviewer=1 "
        "application_rows=0 anon=denied reviewer=guarded worker=scoped "
        "exporter=scoped live_policy_allowlist=empty"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap and verify the approved empty production Supabase foundation."
    )
    parser.add_argument("command", choices=("bootstrap-reviewer", "verify"))
    args = parser.parse_args()
    if os.getenv("SCAM_RADAR_ALLOW_PRODUCTION_SUPABASE") != "true":
        raise RuntimeError(
            "production Supabase is disabled; use only the protected approved workflow"
        )
    if args.command == "bootstrap-reviewer":
        bootstrap_reviewer()
    else:
        verify_foundation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
