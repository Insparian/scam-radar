from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
SEED_PATH = ROOT / "supabase" / "seed.sql"
GENERATOR_PATH = ROOT / "scripts" / "generate_database_types.py"
GENERATED_TYPES_PATH = ROOT / "web" / "lib" / "generated" / "database.types.ts"

EXPECTED_TABLES = {
    "admin_users",
    "sources",
    "source_items",
    "source_item_versions",
    "ai_artifacts",
    "scam_patterns",
    "pattern_revisions",
    "scam_aliases",
    "pattern_evidence",
    "evidence_spans",
    "evidence_claim_support",
    "review_items",
    "pipeline_runs",
    "source_states",
    "source_run_results",
    "review_events",
    "heat_snapshots",
    "public_releases",
    "public_release_items",
    "publication_changes",
    "operation_leases",
}

REVIEWER_FUNCTIONS = {
    "approve_new_pattern",
    "approve_pattern_update",
    "reject_review_item",
    "hold_for_evidence",
    "merge_pattern_candidate",
    "archive_pattern",
    "unpublish_pattern",
}

SERVICE_FUNCTIONS = {
    "prepare_public_release",
    "export_public_release",
    "mark_release_deploying",
    "record_deployed_release",
    "record_release_failure",
}


def load_type_generator():
    spec = importlib.util.spec_from_file_location(
        "database_type_generator", GENERATOR_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load database type generator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DatabaseContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration_paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
        cls.migrations = "\n".join(
            path.read_text(encoding="utf-8") for path in cls.migration_paths
        )
        cls.migrations_lower = cls.migrations.lower()
        cls.seed = SEED_PATH.read_text(encoding="utf-8")
        cls.generator = load_type_generator()
        cls.tables = {
            table.name: table for table in cls.generator.parse_tables(cls.migrations)
        }
        cls.functions = {
            function.name: function
            for function in cls.generator.parse_functions(cls.migrations)
        }

    def test_forward_only_migration_shape(self) -> None:
        self.assertGreaterEqual(len(self.migration_paths), 3)
        names = [path.name for path in self.migration_paths]
        self.assertEqual(names, sorted(names))
        for path in self.migration_paths:
            self.assertRegex(path.name, r"^\d{14}_[a-z0-9_]+\.sql$")
            content = path.read_text(encoding="utf-8").strip().lower()
            self.assertTrue(content.startswith("begin;"), path.name)
            self.assertTrue(content.endswith("commit;"), path.name)
            self.assertNotRegex(content, r"\b(drop\s+table|truncate\s+table)\b")

    def test_core_tables_and_critical_columns_exist(self) -> None:
        self.assertEqual(set(self.tables), EXPECTED_TABLES)
        expected_columns = {
            "source_item_versions": {
                "content_hash",
                "origin_group_key",
                "duplicate_of_version_id",
                "supersedes_version_id",
                "processing_status",
            },
            "pattern_revisions": {
                "revision_no",
                "risk_type",
                "evidence_level",
                "legal_status",
                "evidence_set_hash",
                "content_hash",
                "approved_by",
                "approved_at",
            },
            "pattern_evidence": {
                "origin_group_key",
                "evidence_family_id",
                "acceptance_status",
                "source_status",
            },
            "review_items": {
                "candidate_hash",
                "base_row_version",
                "dedupe_key",
            },
            "public_release_items": {
                "release_id",
                "pattern_id",
                "pattern_revision_id",
                "heat_snapshot_id",
            },
        }
        for table_name, columns in expected_columns.items():
            actual = {column.name for column in self.tables[table_name].columns}
            self.assertTrue(columns <= actual, f"{table_name}: {columns - actual}")

    def test_database_uses_expected_primitive_contract(self) -> None:
        for table in self.tables.values():
            self.assertTrue(
                any(column.name == "created_at" for column in table.columns)
                or table.name
                in {
                    "evidence_claim_support",
                    "pipeline_runs",
                    "source_states",
                    "heat_snapshots",
                    "public_releases",
                    "operation_leases",
                }
            )
        self.assertNotRegex(self.migrations_lower, r"create\s+type\s+public\.")
        self.assertNotIn("timestamp without time zone", self.migrations_lower)
        self.assertNotIn("serial primary key", self.migrations_lower)

    def test_jsonb_storage_is_narrow_and_versioned(self) -> None:
        json_columns = {
            (table.name, column.name)
            for table in self.tables.values()
            for column in table.columns
            if column.ts_type == "Json"
        }
        self.assertEqual(
            json_columns,
            {
                ("sources", "parser_config"),
                ("ai_artifacts", "result"),
                ("ai_artifacts", "usage"),
                ("review_items", "candidate_payload"),
                ("heat_snapshots", "breakdown"),
            },
        )
        self.assertIn(
            "candidate_schema_version",
            {c.name for c in self.tables["review_items"].columns},
        )
        self.assertIn(
            "schema_version", {c.name for c in self.tables["ai_artifacts"].columns}
        )

    def test_all_public_tables_have_rls_and_deny_direct_browser_access(self) -> None:
        for table_name in EXPECTED_TABLES:
            self.assertRegex(
                self.migrations_lower,
                rf"alter\s+table\s+public\.{table_name}\s+enable\s+row\s+level\s+security",
            )
        self.assertIn(
            "revoke all on all tables in schema public from public, anon, authenticated",
            self.migrations_lower,
        )
        self.assertNotRegex(
            self.migrations_lower,
            r"grant\s+(select|insert|update|delete).*\bto\s+(anon|authenticated)\b",
        )

    def test_rpc_grants_are_role_specific(self) -> None:
        self.assertEqual(set(self.functions), REVIEWER_FUNCTIONS | SERVICE_FUNCTIONS)
        for function_name in REVIEWER_FUNCTIONS:
            self.assertRegex(
                self.migrations_lower,
                rf"grant\s+execute\s+on\s+function\s+public\.{function_name}\([^;]+\)\s+to\s+authenticated",
            )
            self.assertNotRegex(
                self.migrations_lower,
                rf"grant\s+execute\s+on\s+function\s+public\.{function_name}\([^;]+\)\s+to\s+anon",
            )
        for function_name in SERVICE_FUNCTIONS:
            self.assertRegex(
                self.migrations_lower,
                rf"grant\s+execute\s+on\s+function\s+public\.{function_name}\([^;]+\)\s+to\s+service_role",
            )
            self.assertNotRegex(
                self.migrations_lower,
                rf"grant\s+execute\s+on\s+function\s+public\.{function_name}\([^;]+\)\s+to\s+authenticated",
            )

    def test_every_security_definer_uses_empty_search_path(self) -> None:
        definitions = re.finditer(
            r"create\s+or\s+replace\s+function\s+((?:public|private)\.[a-z_][a-z0-9_]*)\s*\(",
            self.migrations_lower,
        )
        for definition in definitions:
            header_start = definition.start()
            body_start = self.migrations_lower.find("as $$", definition.end())
            self.assertNotEqual(body_start, -1, definition.group(1))
            header = self.migrations_lower[header_start:body_start]
            if "security definer" in header:
                self.assertIn("set search_path = ''", header, definition.group(1))

    def test_reviewer_identity_and_publish_gate_are_database_enforced(self) -> None:
        required_fragments = {
            "auth.uid() is null",
            "reviewer_identity_required",
            "enabled_reviewer_required",
            "candidate_changed",
            "stale_row_version",
            "reviewed_content_changed",
            "evidence_set_changed",
            "evidence_must_start_proposed",
            "publication_requires_human_approved_revision",
            "publication_request_requires_matching_review_event",
            "all_proposed_evidence_requires_decision",
            "authoritative_evidence_required",
            "sources_not_independent",
            "risk_legal_label_incompatible",
            "distinct_regions_required",
            "claim_not_supported",
            "private.revision_public_claims",
        }
        for fragment in required_fragments:
            self.assertIn(fragment, self.migrations_lower)
        self.assertRegex(
            self.migrations_lower,
            re.compile(
                r"new\.revision_status\s*=\s*'approved'.+private\.assert_enabled_admin",
                re.DOTALL,
            ),
        )

    def test_immutable_and_append_only_records_have_triggers(self) -> None:
        required_triggers = {
            "source_item_versions_protect_content",
            "sources_protect_identity",
            "scam_patterns_protect_identity",
            "review_items_protect_resolution",
            "pattern_revisions_protect_approval",
            "scam_aliases_protect_approved_revision",
            "evidence_claim_support_protect_approved_revision",
            "pattern_evidence_protect_resolution",
            "evidence_spans_append_only",
            "review_events_append_only",
            "review_events_require_human_actor",
            "heat_snapshots_append_only",
            "public_release_items_append_only",
            "public_releases_protect_history",
            "publication_changes_protect_history",
            "publication_changes_require_human_request",
        }
        for trigger_name in required_triggers:
            self.assertRegex(
                self.migrations_lower, rf"create\s+trigger\s+{trigger_name}\b"
            )
        self.assertIn("approved_revision_is_immutable", self.migrations_lower)
        self.assertIn("release_manifest_is_immutable", self.migrations_lower)

    def test_deduplication_and_cross_row_integrity_are_explicit(self) -> None:
        required_fragments = {
            "unique (source_id, identity_key)",
            "unique (source_item_id, content_hash)",
            "source_item_versions_content_hash_idx",
            "review_items_open_dedupe_unique",
            "where status in ('pending', 'in_review', 'needs_evidence')",
            "evidence_claim_support_span_evidence_fk",
            "public_release_items_revision_pattern_fk",
            "release_heat_pattern_mismatch",
        }
        for fragment in required_fragments:
            self.assertIn(fragment, self.migrations_lower)

    def test_release_contract_pins_exact_revision_and_heat(self) -> None:
        required_fragments = {
            "previous_item.pattern_revision_id",
            "previous_item.heat_snapshot_id",
            "latest_change.pattern_revision_id",
            "state in ('approved', 'deploying', 'deployed_unrecorded', 'deployed', 'superseded')",
            "deployed_release_changed",
            "release_already_pending",
            "older_release_cannot_overwrite_newer",
            "public-release-v1",
            "pattern_revision_id",
            "heat_snapshot_id",
            "manifest_hash",
        }
        for fragment in required_fragments:
            self.assertIn(fragment, self.migrations_lower)
        export_start = self.migrations_lower.index(
            "function public.export_public_release"
        )
        export_end = self.migrations_lower.index(
            "function public.mark_release_deploying"
        )
        export_body = self.migrations_lower[export_start:export_end]
        self.assertNotIn("clean_text", export_body)
        self.assertNotIn("evidence_spans", export_body)
        self.assertNotIn("candidate_payload", export_body)
        self.assertNotIn("source_status", export_body)
        self.assertNotIn("last_verified_at", export_body)

    def test_merge_skeleton_fails_closed_instead_of_mutating_evidence(self) -> None:
        merge_start = self.migrations_lower.index(
            "function public.merge_pattern_candidate"
        )
        merge_end = self.migrations_lower.index("function public.archive_pattern")
        merge_body = self.migrations_lower[merge_start:merge_end]
        self.assertIn("merge_requires_reviewed_destination_revision", merge_body)
        self.assertNotRegex(merge_body, r"update\s+public\.pattern_evidence")

    def test_seed_is_synthetic_and_cannot_bypass_human_approval(self) -> None:
        urls = re.findall(r"https://[^'\s]+", self.seed)
        self.assertTrue(urls)
        self.assertTrue(all(".example.invalid/" in url for url in urls), urls)
        self.assertNotRegex(
            self.seed.lower(), r"insert\s+into\s+(?:auth\.users|public\.admin_users)"
        )
        self.assertNotRegex(self.seed.lower(), r"'approved'\s*,\s*\n\s*'[^']+scam")
        self.assertNotRegex(
            self.seed.lower(), r"insert\s+into\s+public\.public_releases"
        )
        self.assertNotIn("@", self.seed)

    def test_source_storage_has_hash_but_no_raw_response_column(self) -> None:
        columns = {
            column.name for column in self.tables["source_item_versions"].columns
        }
        self.assertIn("raw_html_hash", columns)
        self.assertNotIn("raw_html", columns)
        self.assertNotIn("response_headers", columns)
        self.assertNotIn("screenshot", columns)

    def test_generated_types_match_migrations(self) -> None:
        result = subprocess.run(
            [sys.executable, str(GENERATOR_PATH), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = GENERATED_TYPES_PATH.read_text(encoding="utf-8")
        for table_name in EXPECTED_TABLES:
            self.assertRegex(
                generated, re.compile(rf"^      {table_name}: \{{", re.MULTILINE)
            )
        for function_name in REVIEWER_FUNCTIONS | SERVICE_FUNCTIONS:
            self.assertRegex(
                generated, re.compile(rf"^      {function_name}: \{{", re.MULTILINE)
            )


if __name__ == "__main__":
    unittest.main()
