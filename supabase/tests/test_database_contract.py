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
    "evidence_resolution_events",
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
    "public_release_evidence_items",
    "publication_changes",
    "operation_leases",
    "policy_decisions",
}

REVIEWER_FUNCTIONS = {
    "get_reviewer_bootstrap",
    "reject_review_item",
    "hold_for_evidence",
    "merge_pattern_candidate",
    "archive_pattern",
    "unpublish_pattern",
    "confirm_policy_publication",
}

SERVICE_FUNCTIONS = {
    "prepare_public_release",
    "export_public_release",
    "mark_release_deploying",
    "record_deployed_release",
    "record_release_failure",
    "record_policy_decision",
    "apply_live_policy_publication",
}

DISABLED_LEGACY_PUBLISH_FUNCTIONS = {
    "approve_new_pattern",
    "approve_pattern_update",
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
        self.assertGreaterEqual(len(self.migration_paths), 4)
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
                "verified_at",
                "verification_path",
                "verification_policy_decision_id",
                "verification_review_event_id",
            },
            "pattern_evidence": {
                "origin_group_key",
                "evidence_family_id",
                "acceptance_status",
                "source_status",
                "acceptance_path",
                "acceptance_policy_decision_id",
            },
            "evidence_resolution_events": {
                "pattern_evidence_id",
                "outcome",
                "authority_path",
                "actor_id",
                "policy_decision_id",
                "review_item_id",
                "reason",
                "reason_codes",
                "occurred_at",
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
                "last_verified_at",
            },
            "public_release_evidence_items": {
                "release_id",
                "pattern_id",
                "pattern_evidence_id",
                "last_verified_at",
            },
            "public_releases": {
                "schema_version",
                "prepared_at",
                "published_at",
                "deployed_at",
            },
            "publication_changes": {
                "requested_by",
                "review_event_id",
                "request_path",
                "policy_decision_id",
            },
            "policy_decisions": {
                "pattern_id",
                "pattern_revision_id",
                "review_item_id",
                "policy_version",
                "policy_hash",
                "input_hash",
                "gate_outcome",
                "rules_outcome",
                "decision_outcome",
                "execution_mode",
                "publication_authorized",
                "model_confidence_downgrade",
                "reason_codes",
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
        self.assertEqual(
            set(self.functions),
            REVIEWER_FUNCTIONS | SERVICE_FUNCTIONS | DISABLED_LEGACY_PUBLISH_FUNCTIONS,
        )
        for function_name in REVIEWER_FUNCTIONS:
            self.assertRegex(
                self.migrations_lower,
                rf"grant\s+execute\s+on\s+function\s+public\.{function_name}\([^;]*\)\s+to\s+authenticated",
            )
            self.assertNotRegex(
                self.migrations_lower,
                rf"grant\s+execute\s+on\s+function\s+public\.{function_name}\([^;]*\)\s+to\s+anon",
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
        self.assertRegex(
            self.migrations_lower,
            r"revoke\s+execute\s+on\s+function\s+public\.confirm_policy_publication\([^;]+\)\s+from\s+public,\s*anon,\s*service_role",
        )
        for function_name in DISABLED_LEGACY_PUBLISH_FUNCTIONS:
            permission_statements = re.findall(
                rf"(?:grant|revoke)\s+execute\s+on\s+function\s+public\.{function_name}\([^;]+;",
                self.migrations_lower,
            )
            self.assertTrue(permission_statements, function_name)
            self.assertRegex(
                permission_statements[-1],
                rf"^revoke\s+execute\s+on\s+function\s+public\.{function_name}\([^;]+\)\s+from\s+public,\s*anon,\s*authenticated,\s*service_role;\s*$",
                function_name,
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
            "authenticated_reviewer_role_required",
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
            "function public.get_reviewer_bootstrap",
        }
        for fragment in required_fragments:
            self.assertIn(fragment, self.migrations_lower)
        self.assertIn(
            "publication_requires_human_verified_revision", self.migrations_lower
        )
        bootstrap_start = self.migrations_lower.rindex(
            "create or replace function public.get_reviewer_bootstrap"
        )
        bootstrap_end = self.migrations_lower.index("$$;", bootstrap_start)
        bootstrap_body = self.migrations_lower[bootstrap_start:bootstrap_end]
        self.assertIn("private.assert_enabled_admin(actor_id)", bootstrap_body)
        self.assertNotIn("clean_text", bootstrap_body)
        self.assertNotIn("evidence_spans", bootstrap_body)
        self.assertNotIn("candidate_payload", bootstrap_body)
        self.assertRegex(
            self.migrations_lower,
            re.compile(
                r"new\.revision_status\s*=\s*'approved'.+private\.assert_enabled_admin",
                re.DOTALL,
            ),
        )
        reviewer_guard_start = self.migrations_lower.rindex(
            "function private.assert_enabled_admin"
        )
        reviewer_guard_end = self.migrations_lower.index("$$;", reviewer_guard_start)
        reviewer_guard_body = self.migrations_lower[
            reviewer_guard_start:reviewer_guard_end
        ]
        self.assertIn("jwt_role is distinct from 'authenticated'", reviewer_guard_body)

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
            "evidence_resolution_events_validate_insert",
            "evidence_resolution_events_append_only",
            "evidence_spans_append_only",
            "review_events_append_only",
            "review_events_require_human_actor",
            "heat_snapshots_append_only",
            "public_release_items_append_only",
            "public_releases_protect_history",
            "publication_changes_protect_history",
            "publication_changes_require_human_request",
            "policy_decisions_validate_insert",
            "policy_decisions_append_only",
            "public_release_evidence_items_validate_insert",
            "public_release_evidence_items_append_only",
        }
        for trigger_name in required_triggers:
            self.assertRegex(
                self.migrations_lower, rf"create\s+trigger\s+{trigger_name}\b"
            )
        self.assertIn("approved_revision_is_immutable", self.migrations_lower)
        self.assertIn("release_manifest_is_immutable", self.migrations_lower)
        self.assertIn(
            "rename to publication_changes_require_authorized_request",
            self.migrations_lower,
        )
        self.assertIn(
            "legacy_resolution_events_are_migration_only", self.migrations_lower
        )
        self.assertIn("evidence_resolution_context_required", self.migrations_lower)
        self.assertIn(
            "pre_migration_resolution_provenance_unavailable", self.migrations_lower
        )
        legacy_backfill = self.migrations_lower.index(
            "insert into public.evidence_resolution_events"
        )
        insert_guard = self.migrations_lower.index(
            "create trigger evidence_resolution_events_validate_insert"
        )
        self.assertLess(legacy_backfill, insert_guard)

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
            "private.revision_last_verified_at(previous_item.pattern_revision_id)",
            "latest_change.pattern_revision_id",
            "state in ('approved', 'deploying', 'deployed_unrecorded', 'deployed', 'superseded')",
            "deployed_release_changed",
            "release_already_pending",
            "older_release_cannot_overwrite_newer",
            "'schema_version', 2",
            "pattern_revision_id",
            "heat_snapshot_id",
            "public_release_evidence_items",
            "manifest_hash",
        }
        for fragment in required_fragments:
            self.assertIn(fragment, self.migrations_lower)
        export_start = self.migrations_lower.rindex(
            "create or replace function public.export_public_release"
        )
        export_end = self.migrations_lower.index("$$;", export_start)
        export_body = self.migrations_lower[export_start:export_end]
        self.assertNotIn("clean_text", export_body)
        self.assertNotIn("evidence_spans", export_body)
        self.assertNotIn("candidate_payload", export_body)
        self.assertNotIn("source_status", export_body)
        self.assertNotIn("verification_path", export_body)
        self.assertNotIn("approved_by", export_body)
        self.assertNotIn("accepted_by", export_body)
        self.assertIn("'published_at', release.published_at", export_body)
        self.assertIn("'verified_at', revision.verified_at", export_body)
        self.assertIn("'last_verified_at', item.last_verified_at", export_body)
        self.assertIn("'last_verified_at', snapshot.last_verified_at", export_body)

    def test_policy_decisions_fail_closed_and_keep_human_provenance_distinct(
        self,
    ) -> None:
        required_fragments = {
            "safe_to_automate",
            "review_required",
            "eligible_for_policy",
            "policy_decisions_never_increase_authority",
            "policy_decisions_confidence_only_downgrades",
            "policy_decisions_gate_authority",
            "policy_decisions_publication_authority",
            "policy_decisions_behavior_unique",
            "policy_decisions_append_only",
            "policy_decision_replay_mismatch",
            "active_live_publication_policies",
            "policy_live_publication_policy_inactive",
            "current_policy_provenance_required",
            "policy_decision_not_valid_human_exception",
            "verification_path = 'human'",
            "verification_path = 'policy'",
            "acceptance_path = 'human'",
            "acceptance_path = 'policy'",
            "request_path = 'human'",
            "request_path = 'policy'",
            "verification_review_event_id",
        }
        for fragment in required_fragments:
            self.assertIn(fragment, self.migrations_lower)

        active_policy_start = self.migrations_lower.rindex(
            "function private.active_live_publication_policies"
        )
        active_policy_end = self.migrations_lower.index("$$;", active_policy_start)
        active_policy_body = self.migrations_lower[
            active_policy_start:active_policy_end
        ]
        self.assertIn(
            "returns table (policy_version text, policy_hash text, gate_version text)",
            active_policy_body,
        )
        self.assertIn("where false", active_policy_body)

        insert_guard_start = self.migrations_lower.rindex(
            "create or replace function private.validate_policy_decision_insert"
        )
        insert_guard_end = self.migrations_lower.index("$$;", insert_guard_start)
        insert_guard_body = self.migrations_lower[insert_guard_start:insert_guard_end]
        for tuple_field in ("policy_version", "policy_hash", "gate_version"):
            self.assertIn(
                f"active_policy.{tuple_field} = new.{tuple_field}",
                insert_guard_body,
            )

        record_start = self.migrations_lower.rindex(
            "create or replace function public.record_policy_decision"
        )
        record_end = self.migrations_lower.index("$$;", record_start)
        record_body = self.migrations_lower[record_start:record_end]
        for tuple_field in ("policy_version", "policy_hash", "gate_version"):
            self.assertIn(
                f"active_policy.{tuple_field} = p_{tuple_field}",
                record_body,
            )
        self.assertIn("pipeline_run_id = p_pipeline_run_id", record_body)
        self.assertIn("policy_decision_conflict_not_found", record_body)
        self.assertGreaterEqual(
            record_body.count("policy_decision_replay_mismatch"),
            2,
            "both ordinary replay and concurrent conflict paths must compare the full payload",
        )

        live_assert_start = self.migrations_lower.rindex(
            "create or replace function private.assert_live_policy_execution"
        )
        live_assert_end = self.migrations_lower.index("$$;", live_assert_start)
        live_assert_body = self.migrations_lower[live_assert_start:live_assert_end]
        for tuple_field in ("policy_version", "policy_hash", "gate_version"):
            self.assertIn(
                f"active_policy.{tuple_field} = decision.{tuple_field}",
                live_assert_body,
            )

        exception_start = self.migrations_lower.rindex(
            "create or replace function private.assert_human_policy_exception"
        )
        exception_end = self.migrations_lower.index("$$;", exception_start)
        exception_body = self.migrations_lower[exception_start:exception_end]
        self.assertIn("decision.execution_mode = 'shadow'", exception_body)
        self.assertIn("decision.execution_mode = 'live'", exception_body)
        self.assertIn("decision.decision_outcome = 'review_required'", exception_body)
        self.assertIn("decision.decision_outcome = 'blocked'", exception_body)
        self.assertIn("not decision.publication_authorized", exception_body)

        confirm_start = self.migrations_lower.rindex(
            "create or replace function public.confirm_policy_publication"
        )
        confirm_end = self.migrations_lower.index("$$;", confirm_start)
        confirm_body = self.migrations_lower[confirm_start:confirm_end]
        self.assertIn("private.assert_enabled_admin(auth.uid())", confirm_body)
        self.assertIn("private.assert_human_policy_exception", confirm_body)

        private_approve_start = self.migrations_lower.rindex(
            "create or replace function private.approve_review_item"
        )
        private_approve_end = self.migrations_lower.index("$$;", private_approve_start)
        private_approve_body = self.migrations_lower[
            private_approve_start:private_approve_end
        ]
        self.assertIn(
            "if exception_policy_decision_id is null then", private_approve_body
        )
        self.assertIn("human_policy_exception_context_required", private_approve_body)
        self.assertNotIn(
            "if exception_policy_decision_id is not null then", private_approve_body
        )
        exception_assert_index = private_approve_body.index(
            "perform private.assert_human_policy_exception"
        )
        evidence_update_index = private_approve_body.index(
            "perform private.apply_evidence_decisions"
        )
        self.assertLess(exception_assert_index, evidence_update_index)

        live_start = self.migrations_lower.rindex(
            "create or replace function public.apply_live_policy_publication"
        )
        live_end = self.migrations_lower.index("$$;", live_start)
        live_body = self.migrations_lower[live_start:live_end]
        self.assertIn("private.assert_trusted_service()", live_body)
        self.assertNotIn("private.append_review_event", live_body)
        self.assertIn("approved_by = null", live_body)
        self.assertIn("not decision.publication_authorized", self.migrations_lower)
        self.assertIn("requested_by", live_body)

        pipeline_run_column = next(
            column
            for column in self.tables["policy_decisions"].columns
            if column.name == "pipeline_run_id"
        )
        self.assertFalse(pipeline_run_column.nullable)

    def test_public_freshness_is_conservative_and_release_pinned(self) -> None:
        freshness_start = self.migrations_lower.rindex(
            "function private.revision_last_verified_at"
        )
        freshness_end = self.migrations_lower.index("$$;", freshness_start)
        freshness_body = self.migrations_lower[freshness_start:freshness_end]
        self.assertIn("select distinct support.pattern_evidence_id", freshness_body)
        self.assertIn("count(evidence.last_verified_at) <> count(*)", freshness_body)
        self.assertIn("min(evidence.last_verified_at)", freshness_body)

        approval_freshness_start = self.migrations_lower.rindex(
            "function private.assert_public_claim_evidence_verified"
        )
        approval_freshness_end = self.migrations_lower.index(
            "$$;", approval_freshness_start
        )
        approval_freshness_body = self.migrations_lower[
            approval_freshness_start:approval_freshness_end
        ]
        self.assertIn("private.revision_public_claims", approval_freshness_body)
        self.assertIn(
            "evidence.acceptance_status = 'accepted'", approval_freshness_body
        )
        self.assertIn("evidence.last_verified_at is null", approval_freshness_body)
        self.assertIn(
            "perform private.assert_public_claim_evidence_verified(new.id)",
            self.migrations_lower,
        )

        release_item_validator_start = self.migrations_lower.rindex(
            "function private.validate_release_item"
        )
        release_item_validator_end = self.migrations_lower.index(
            "$$;", release_item_validator_start
        )
        release_item_validator_body = self.migrations_lower[
            release_item_validator_start:release_item_validator_end
        ]
        self.assertIn("new.last_verified_at is null", release_item_validator_body)
        self.assertIn(
            "revision.verified_at > release.published_at",
            release_item_validator_body,
        )
        self.assertIn(
            "new.last_verified_at > release.published_at",
            release_item_validator_body,
        )

        release_evidence_column = next(
            column
            for column in self.tables["public_release_evidence_items"].columns
            if column.name == "last_verified_at"
        )
        self.assertFalse(release_evidence_column.nullable)
        self.assertIn(
            "new.last_verified_at <= release.published_at",
            self.migrations_lower,
        )
        self.assertNotRegex(
            self.migrations_lower,
            r"evidence\.last_verified_at\s*(?:<=|<)\s*revision\.verified_at",
        )

        prepare_start = self.migrations_lower.rindex(
            "function public.prepare_public_release"
        )
        prepare_end = self.migrations_lower.index("$$;", prepare_start)
        prepare_body = self.migrations_lower[prepare_start:prepare_end]
        self.assertIn("release_published_at", prepare_body)
        self.assertIn("public_release_evidence_items", prepare_body)
        self.assertIn("item.last_verified_at", prepare_body)
        self.assertIn("snapshot.last_verified_at", prepare_body)

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
        self.assertRegex(
            generated,
            re.compile(r"^\s+reason_codes: string\[\]$", re.MULTILINE),
        )
        record_rpc_start = generated.index("      record_policy_decision: {")
        record_rpc_end = generated.index(
            "      confirm_policy_publication: {", record_rpc_start
        )
        record_rpc = generated[record_rpc_start:record_rpc_end]
        self.assertRegex(
            record_rpc,
            re.compile(r"^\s+p_pipeline_run_id: string$", re.MULTILINE),
        )
        self.assertNotRegex(
            record_rpc,
            re.compile(r"^\s+p_pipeline_run_id\?:", re.MULTILINE),
        )
        self.assertRegex(
            record_rpc,
            re.compile(r"^\s+p_model_confidence\?: number \| null$", re.MULTILINE),
        )
        for table_name in EXPECTED_TABLES:
            self.assertRegex(
                generated, re.compile(rf"^      {table_name}: \{{", re.MULTILINE)
            )
        for function_name in (
            REVIEWER_FUNCTIONS | SERVICE_FUNCTIONS | DISABLED_LEGACY_PUBLISH_FUNCTIONS
        ):
            self.assertRegex(
                generated, re.compile(rf"^      {function_name}: \{{", re.MULTILINE)
            )


if __name__ == "__main__":
    unittest.main()
