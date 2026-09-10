from __future__ import annotations

from pathlib import Path

from scripts.check_public_boundary import boundary_failures
from scripts.check_secrets import content_findings


def test_secret_scan_reports_types_without_echoing_values() -> None:
    secret = "ghp_" + "abcdefghijklmnopqrstuvwxyz1234567890"

    findings = content_findings(f"token={secret}", export=False)

    assert findings == ["GitHub token"]
    assert secret not in " ".join(findings)


def test_static_export_rejects_private_variable_names() -> None:
    assert content_findings("SUPABASE_SECRET_KEY", export=True) == [
        "private variable name SUPABASE_SECRET_KEY"
    ]


def test_public_boundary_blocks_private_and_generated_files() -> None:
    failures = boundary_failures(
        [Path(".env.production"), Path("work/release.json"), Path("backup.dump")]
    )

    assert len(failures) == 3


def test_public_boundary_allows_documentation_and_fake_env_template() -> None:
    assert boundary_failures([Path("docs/architecture.md"), Path(".env.example")]) == []
