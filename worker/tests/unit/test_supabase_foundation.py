from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from scripts import supabase_foundation


def test_parse_single_json_row() -> None:
    expected = {"migrations_ok": True, "one_reviewer": True}
    result = subprocess.CompletedProcess(
        args=["psql"], returncode=0, stdout=json.dumps(expected) + "\n", stderr=""
    )

    assert supabase_foundation.parse_single_json_row(result) == expected


def test_bootstrap_reviewer_withholds_database_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["psql"], returncode=1, stdout="private row", stderr="private error"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="output was withheld") as error:
        supabase_foundation.run_psql(
            "postgresql://private", "select 1", variables={"reviewer_email": "private"}
        )

    assert "private" not in str(error.value)


def test_bootstrap_requires_existing_auth_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_REVIEWER_EMAIL", "reviewer@example.com")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://private")
    monkeypatch.setattr(
        supabase_foundation,
        "run_psql",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["psql"], returncode=0, stdout="0\n", stderr=""
        ),
    )

    with pytest.raises(RuntimeError, match="pre-created"):
        supabase_foundation.bootstrap_reviewer()


def test_bootstrap_maps_exactly_one_auth_user(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("SUPABASE_REVIEWER_EMAIL", "reviewer@example.com")
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://private")
    monkeypatch.setattr(
        supabase_foundation,
        "run_psql",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["psql"],
            returncode=0,
            stdout="1\n",
            stderr="",
        ),
    )

    supabase_foundation.bootstrap_reviewer()

    assert "reviewer@example.com" not in capsys.readouterr().out


def test_bootstrap_query_returns_only_the_upsert_count() -> None:
    assert "with upserted_reviewer as" in supabase_foundation.BOOTSTRAP_REVIEWER_SQL
    assert "select count(*)" in supabase_foundation.BOOTSTRAP_REVIEWER_SQL


def test_production_guard_is_closed_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCAM_RADAR_ALLOW_PRODUCTION_SUPABASE", raising=False)
    monkeypatch.setattr("sys.argv", ["supabase_foundation.py", "verify"])

    with pytest.raises(RuntimeError, match="disabled"):
        supabase_foundation.main()


def test_foundation_query_checks_private_live_policy_allowlist() -> None:
    assert "private.active_live_publication_policies()" in (supabase_foundation.FOUNDATION_QUERY)
    assert "public.active_live_publication_policies()" not in (supabase_foundation.FOUNDATION_QUERY)


def test_foundation_query_requires_reviewer_bootstrap_migration_and_grant() -> None:
    assert "'20260916000200'" in supabase_foundation.FOUNDATION_QUERY
    assert "'public.get_reviewer_bootstrap()'" in supabase_foundation.FOUNDATION_QUERY
    assert "reviewer_bootstrap_only_authenticated" in supabase_foundation.FOUNDATION_QUERY


def test_service_role_lockdown_is_forward_only() -> None:
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "20260916000100_service_role_table_lockdown.sql"
    ).read_text()

    assert "revoke all on all tables in schema public from service_role" in migration
    assert "revoke all on all sequences in schema public from service_role" in migration
    assert "alter default privileges" in migration
