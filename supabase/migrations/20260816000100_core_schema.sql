begin;

create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;
create schema if not exists private;

revoke all on schema private from public;

create table public.admin_users (
    user_id uuid primary key references auth.users (id) on delete restrict,
    role text not null default 'reviewer' check (role in ('reviewer', 'admin')),
    enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.sources (
    id uuid primary key default extensions.gen_random_uuid(),
    source_key text not null unique check (source_key ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
    name text not null check (btrim(name) <> ''),
    domain text not null check (domain ~ '^[a-z0-9.-]+$'),
    publisher_group text not null check (btrim(publisher_group) <> ''),
    source_type text not null check (source_type in ('police', 'regulator', 'court', 'state_media', 'media')),
    authority_tier text not null check (authority_tier in ('A1', 'A2', 'B', 'C')),
    ingestion_method text not null check (ingestion_method in ('rss', 'api', 'sitemap', 'list_page', 'html_polling')),
    entry_url text not null check (entry_url ~ '^https://'),
    enabled boolean not null default false,
    poll_frequency text not null default 'three_daily' check (poll_frequency in ('three_daily', 'daily', 'weekly', 'manual')),
    parser_config jsonb not null default '{}'::jsonb check (jsonb_typeof(parser_config) = 'object'),
    config_hash text not null check (config_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    synced_at timestamptz not null default now()
);

create table public.source_items (
    id uuid primary key default extensions.gen_random_uuid(),
    source_id uuid not null references public.sources (id) on delete restrict,
    external_id text,
    identity_key text not null check (btrim(identity_key) <> ''),
    canonical_url text not null check (canonical_url ~ '^https://'),
    current_version_id uuid,
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint source_items_seen_order check (last_seen_at >= first_seen_at),
    constraint source_items_source_identity_unique unique (source_id, identity_key),
    constraint source_items_id_source_unique unique (id, source_id)
);

create table public.source_item_versions (
    id uuid primary key default extensions.gen_random_uuid(),
    source_item_id uuid not null references public.source_items (id) on delete restrict,
    url text not null check (url ~ '^https://'),
    canonical_url text not null check (canonical_url ~ '^https://'),
    title text not null check (btrim(title) <> ''),
    author text,
    language text,
    published_at timestamptz,
    fetched_at timestamptz not null,
    clean_text text,
    text_truncated boolean not null default false,
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    raw_html_hash text check (raw_html_hash is null or raw_html_hash ~ '^[0-9a-f]{64}$'),
    origin_group_key text not null check (btrim(origin_group_key) <> ''),
    duplicate_of_version_id uuid references public.source_item_versions (id) on delete restrict,
    supersedes_version_id uuid,
    processing_status text not null default 'pending_ai' check (
        processing_status in ('pending_ai', 'processing', 'processed', 'irrelevant', 'blocked', 'error')
    ),
    attempt_count integer not null default 0 check (attempt_count >= 0),
    last_error text,
    created_at timestamptz not null default now(),
    constraint source_item_versions_content_unique unique (source_item_id, content_hash),
    constraint source_item_versions_id_item_unique unique (id, source_item_id),
    constraint source_item_versions_not_self_duplicate check (duplicate_of_version_id is null or duplicate_of_version_id <> id),
    constraint source_item_versions_not_self_supersede check (supersedes_version_id is null or supersedes_version_id <> id),
    constraint source_item_versions_error_shape check (
        (processing_status = 'error' and last_error is not null)
        or (processing_status <> 'error')
    ),
    constraint source_item_versions_supersedes_same_item foreign key (supersedes_version_id, source_item_id)
        references public.source_item_versions (id, source_item_id) on delete restrict
);

alter table public.source_items
    add constraint source_items_current_version_same_item
    foreign key (current_version_id, id)
    references public.source_item_versions (id, source_item_id)
    on delete restrict;

create table public.ai_artifacts (
    id uuid primary key default extensions.gen_random_uuid(),
    source_item_version_id uuid not null references public.source_item_versions (id) on delete restrict,
    stage text not null check (stage in ('relevance', 'extraction', 'pattern_match', 'embedding')),
    provider text not null check (btrim(provider) <> ''),
    model text not null check (btrim(model) <> ''),
    prompt_version text not null check (btrim(prompt_version) <> ''),
    schema_version text not null check (btrim(schema_version) <> ''),
    input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
    status text not null check (status in ('pending', 'success', 'invalid', 'error')),
    result jsonb,
    usage jsonb,
    latency_ms integer check (latency_ms is null or latency_ms >= 0),
    error_code text,
    created_at timestamptz not null default now(),
    constraint ai_artifacts_result_shape check (result is null or jsonb_typeof(result) = 'object'),
    constraint ai_artifacts_usage_shape check (usage is null or jsonb_typeof(usage) = 'object'),
    constraint ai_artifacts_status_shape check (
        (status = 'success' and result is not null and error_code is null)
        or (status in ('invalid', 'error') and error_code is not null)
        or status = 'pending'
    ),
    constraint ai_artifacts_behavior_unique unique (
        source_item_version_id,
        stage,
        provider,
        model,
        prompt_version,
        schema_version,
        input_hash
    )
);

create table public.scam_patterns (
    id uuid primary key default extensions.gen_random_uuid(),
    slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
    lifecycle_status text not null default 'candidate' check (
        lifecycle_status in ('candidate', 'evidence_pending', 'review_ready', 'rejected', 'archived')
    ),
    current_draft_revision_id uuid,
    latest_approved_revision_id uuid,
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    row_version bigint not null default 1 check (row_version > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint scam_patterns_seen_order check (last_seen_at >= first_seen_at),
    constraint scam_patterns_id_unique unique (id)
);

create table public.pattern_revisions (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_id uuid not null references public.scam_patterns (id) on delete restrict,
    revision_no integer not null check (revision_no > 0),
    schema_version text not null check (btrim(schema_version) <> ''),
    revision_status text not null default 'draft' check (revision_status in ('draft', 'approved', 'rejected')),
    canonical_name text not null check (btrim(canonical_name) <> ''),
    short_name text,
    pattern_type text not null check (btrim(pattern_type) <> ''),
    risk_type text not null check (risk_type in ('confirmed_scam', 'risk_alert')),
    evidence_level text not null check (evidence_level in ('A', 'B', 'C', 'D')),
    legal_status text not null check (
        legal_status in ('warning', 'reported_case', 'enforcement', 'charge', 'judgment', 'unknown')
    ),
    public_evidence_label text,
    one_sentence_summary text not null check (btrim(one_sentence_summary) <> ''),
    target_population text[] not null default '{}',
    contact_channels text[] not null default '{}',
    impersonated_identities text[] not null default '{}',
    hooks text[] not null default '{}',
    common_phrases text[] not null default '{}',
    pressure_tactics text[] not null default '{}',
    requested_actions text[] not null default '{}',
    money_paths text[] not null default '{}',
    technology_used text[] not null default '{}',
    warning_signs text[] not null default '{}',
    what_to_do text[] not null default '{}',
    regions text[] not null default '{}',
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    last_material_change_at timestamptz,
    evidence_set_hash text not null check (evidence_set_hash ~ '^[0-9a-f]{64}$'),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    created_by uuid references public.admin_users (user_id) on delete restrict,
    created_at timestamptz not null default now(),
    approved_by uuid references public.admin_users (user_id) on delete restrict,
    approved_at timestamptz,
    constraint pattern_revisions_pattern_number_unique unique (pattern_id, revision_no),
    constraint pattern_revisions_id_pattern_unique unique (id, pattern_id),
    constraint pattern_revisions_seen_order check (last_seen_at >= first_seen_at),
    constraint pattern_revisions_material_change_order check (
        last_material_change_at is null or last_material_change_at between first_seen_at and last_seen_at
    ),
    constraint pattern_revisions_approval_shape check (
        (revision_status = 'approved' and approved_by is not null and approved_at is not null)
        or (revision_status <> 'approved' and approved_by is null and approved_at is null)
    ),
    constraint pattern_revisions_internal_level_not_public check (
        evidence_level in ('A', 'B') or public_evidence_label is null
    ),
    constraint pattern_revisions_label_matrix check (
        public_evidence_label is null
        or (evidence_level = 'A' and public_evidence_label in (
            '警方通报的诈骗案件',
            '司法机关已公开裁判',
            '监管部门已提示风险'
        ))
        or (evidence_level = 'B' and public_evidence_label in (
            '近期多地出现类似套路',
            '值得警惕的新型风险',
            '多家可信来源报道了相似做法'
        ))
    ),
    constraint pattern_revisions_legal_label_matrix check (
        public_evidence_label <> '司法机关已公开裁判' or legal_status = 'judgment'
    ),
    constraint pattern_revisions_risk_legal_matrix check (
        risk_type <> 'risk_alert' or legal_status in ('warning', 'enforcement', 'unknown')
    )
);

alter table public.scam_patterns
    add constraint scam_patterns_current_draft_same_pattern
    foreign key (current_draft_revision_id, id)
    references public.pattern_revisions (id, pattern_id)
    on delete restrict;

alter table public.scam_patterns
    add constraint scam_patterns_latest_approved_same_pattern
    foreign key (latest_approved_revision_id, id)
    references public.pattern_revisions (id, pattern_id)
    on delete restrict;

create table public.scam_aliases (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_revision_id uuid not null references public.pattern_revisions (id) on delete restrict,
    alias text not null check (btrim(alias) <> ''),
    normalized_alias text not null check (btrim(normalized_alias) <> ''),
    alias_type text not null default 'known' check (alias_type in ('known', 'colloquial', 'former', 'search')),
    created_at timestamptz not null default now(),
    constraint scam_aliases_revision_normalized_unique unique (pattern_revision_id, normalized_alias)
);

create table public.pattern_evidence (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_id uuid not null references public.scam_patterns (id) on delete restrict,
    source_item_version_id uuid not null references public.source_item_versions (id) on delete restrict,
    evidence_type text not null check (evidence_type in ('official_notice', 'judgment', 'enforcement', 'case_report', 'risk_warning', 'media_report')),
    origin_group_key text not null check (btrim(origin_group_key) <> ''),
    evidence_family_id uuid,
    claim_summary text not null check (btrim(claim_summary) <> ''),
    event_date date,
    region text,
    victim_count integer check (victim_count is null or victim_count >= 0),
    loss_amount numeric(18, 2) check (loss_amount is null or loss_amount >= 0),
    new_tactic boolean not null default false,
    new_channel boolean not null default false,
    new_target boolean not null default false,
    new_script boolean not null default false,
    is_material_update boolean not null default false,
    acceptance_status text not null default 'proposed' check (acceptance_status in ('proposed', 'accepted', 'rejected')),
    accepted_by uuid references public.admin_users (user_id) on delete restrict,
    accepted_at timestamptz,
    last_verified_at timestamptz,
    recheck_due_at timestamptz,
    source_status text not null default 'available' check (
        source_status in ('available', 'changed', 'corrected', 'withdrawn', 'unavailable')
    ),
    created_at timestamptz not null default now(),
    constraint pattern_evidence_item_unique unique (pattern_id, source_item_version_id),
    constraint pattern_evidence_acceptance_shape check (
        (acceptance_status = 'accepted' and accepted_by is not null and accepted_at is not null and evidence_family_id is not null)
        or (acceptance_status <> 'accepted' and accepted_by is null and accepted_at is null)
    ),
    constraint pattern_evidence_recheck_order check (
        recheck_due_at is null or last_verified_at is null or recheck_due_at >= last_verified_at
    )
);

create table public.evidence_spans (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_evidence_id uuid not null references public.pattern_evidence (id) on delete restrict,
    start_offset integer not null check (start_offset >= 0),
    end_offset integer not null check (end_offset > start_offset),
    excerpt text not null check (char_length(excerpt) between 1 and 600),
    excerpt_hash text not null check (excerpt_hash ~ '^[0-9a-f]{64}$'),
    created_at timestamptz not null default now(),
    constraint evidence_spans_evidence_offsets_unique unique (pattern_evidence_id, start_offset, end_offset),
    constraint evidence_spans_id_evidence_unique unique (id, pattern_evidence_id)
);

create table public.evidence_claim_support (
    pattern_revision_id uuid not null references public.pattern_revisions (id) on delete restrict,
    field_path text not null check (field_path ~ '^[a-z][a-z0-9_]*(?:\[[1-9][0-9]*\])?$'),
    value_hash text not null check (value_hash ~ '^[0-9a-f]{64}$'),
    pattern_evidence_id uuid not null references public.pattern_evidence (id) on delete restrict,
    evidence_span_id uuid not null references public.evidence_spans (id) on delete restrict,
    created_at timestamptz not null default now(),
    primary key (pattern_revision_id, field_path, value_hash, pattern_evidence_id, evidence_span_id),
    constraint evidence_claim_support_span_evidence_fk foreign key (evidence_span_id, pattern_evidence_id)
        references public.evidence_spans (id, pattern_evidence_id) on delete restrict
);

create table public.review_items (
    id uuid primary key default extensions.gen_random_uuid(),
    review_type text not null check (
        review_type in ('new_pattern', 'pattern_update', 'merge', 'evidence_change', 'public_copy', 'gate_regression', 'source_health')
    ),
    target_id uuid not null,
    status text not null default 'pending' check (
        status in ('pending', 'in_review', 'needs_evidence', 'approved', 'rejected', 'merged')
    ),
    priority smallint not null check (priority between 0 and 100),
    heat_at_creation smallint check (heat_at_creation is null or heat_at_creation between 0 and 100),
    evidence_level_at_creation text check (evidence_level_at_creation is null or evidence_level_at_creation in ('A', 'B', 'C', 'D')),
    reason_codes text[] not null default '{}',
    candidate_schema_version text not null check (btrim(candidate_schema_version) <> ''),
    candidate_payload jsonb not null check (jsonb_typeof(candidate_payload) = 'object'),
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    base_row_version bigint not null check (base_row_version > 0),
    dedupe_key text not null check (btrim(dedupe_key) <> ''),
    assigned_to uuid references public.admin_users (user_id) on delete restrict,
    decision_note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    resolved_at timestamptz,
    constraint review_items_resolution_shape check (
        (status in ('approved', 'rejected', 'merged') and resolved_at is not null and decision_note is not null)
        or (status not in ('approved', 'rejected', 'merged') and resolved_at is null)
    )
);

create table public.pipeline_runs (
    id uuid primary key default extensions.gen_random_uuid(),
    github_run_id text,
    github_run_attempt integer check (github_run_attempt is null or github_run_attempt > 0),
    trigger text not null check (trigger in ('fixture', 'schedule', 'manual', 'ci')),
    commit_sha text not null check (commit_sha ~ '^[0-9a-f]{7,64}$'),
    registry_hash text not null check (registry_hash ~ '^[0-9a-f]{64}$'),
    pipeline_version text not null,
    behavior_hash text not null check (behavior_hash ~ '^[0-9a-f]{64}$'),
    discovered_count integer not null default 0 check (discovered_count >= 0),
    relevant_count integer not null default 0 check (relevant_count >= 0),
    review_count integer not null default 0 check (review_count >= 0),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    outcome text not null default 'running' check (outcome in ('running', 'success', 'degraded', 'failed', 'cancelled')),
    error_summary text,
    constraint pipeline_runs_time_order check (finished_at is null or finished_at >= started_at),
    constraint pipeline_runs_outcome_shape check (
        (outcome = 'running' and finished_at is null)
        or (outcome <> 'running' and finished_at is not null)
    )
);

create table public.source_states (
    source_id uuid primary key references public.sources (id) on delete restrict,
    cursor_value text,
    etag text,
    last_modified text,
    last_attempt_at timestamptz,
    last_success_at timestamptz,
    consecutive_failures integer not null default 0 check (consecutive_failures >= 0),
    last_error_code text,
    updated_at timestamptz not null default now(),
    constraint source_states_attempt_order check (
        last_success_at is null or last_attempt_at is null or last_success_at <= last_attempt_at
    )
);

create table public.source_run_results (
    id uuid primary key default extensions.gen_random_uuid(),
    pipeline_run_id uuid not null references public.pipeline_runs (id) on delete restrict,
    source_id uuid not null references public.sources (id) on delete restrict,
    outcome text not null check (outcome in ('success', 'skipped', 'degraded', 'failed')),
    duration_ms integer not null check (duration_ms >= 0),
    discovered_count integer not null default 0 check (discovered_count >= 0),
    fetched_count integer not null default 0 check (fetched_count >= 0),
    inserted_count integer not null default 0 check (inserted_count >= 0),
    retry_count integer not null default 0 check (retry_count >= 0),
    error_category text,
    created_at timestamptz not null default now(),
    constraint source_run_results_run_source_unique unique (pipeline_run_id, source_id),
    constraint source_run_results_error_shape check (
        (outcome in ('degraded', 'failed') and error_category is not null)
        or outcome in ('success', 'skipped')
    )
);

create table public.review_events (
    id uuid primary key default extensions.gen_random_uuid(),
    actor_id uuid not null references public.admin_users (user_id) on delete restrict,
    action text not null check (btrim(action) <> ''),
    target_type text not null check (target_type in ('review_item', 'pattern', 'pattern_revision', 'evidence', 'release')),
    target_id uuid not null,
    before_state text,
    after_state text,
    reason text not null check (btrim(reason) <> ''),
    event_schema_version text not null default 'review-event-v1',
    created_at timestamptz not null default now()
);

create table public.heat_snapshots (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_id uuid not null references public.scam_patterns (id) on delete restrict,
    score_version text not null check (btrim(score_version) <> ''),
    as_of date not null,
    score smallint not null check (score between 0 and 100),
    breakdown jsonb not null check (jsonb_typeof(breakdown) = 'object'),
    input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
    calculated_at timestamptz not null default now(),
    constraint heat_snapshots_input_unique unique (pattern_id, score_version, as_of, input_hash)
);

create table public.public_releases (
    id uuid primary key default extensions.gen_random_uuid(),
    release_no bigint generated always as identity unique,
    state text not null default 'approved' check (
        state in ('approved', 'deploying', 'deployed_unrecorded', 'deployed', 'deploy_failed', 'superseded')
    ),
    manifest_hash text check (manifest_hash is null or manifest_hash ~ '^[0-9a-f]{64}$'),
    artifact_hash text check (artifact_hash is null or artifact_hash ~ '^[0-9a-f]{64}$'),
    commit_sha text check (commit_sha is null or commit_sha ~ '^[0-9a-f]{7,64}$'),
    deployment_id text,
    previous_deployment_id text,
    prepared_at timestamptz not null default now(),
    deploy_started_at timestamptz,
    deployed_at timestamptz,
    superseded_at timestamptz,
    redacted_error text,
    created_by uuid references public.admin_users (user_id) on delete restrict,
    constraint public_releases_deployed_shape check (
        state not in ('deployed', 'superseded')
        or (manifest_hash is not null and artifact_hash is not null and deployment_id is not null and deployed_at is not null)
    )
);

create table public.public_release_items (
    release_id uuid not null references public.public_releases (id) on delete restrict,
    pattern_id uuid not null references public.scam_patterns (id) on delete restrict,
    pattern_revision_id uuid not null,
    heat_snapshot_id uuid not null references public.heat_snapshots (id) on delete restrict,
    created_at timestamptz not null default now(),
    primary key (release_id, pattern_id),
    constraint public_release_items_revision_pattern_fk foreign key (pattern_revision_id, pattern_id)
        references public.pattern_revisions (id, pattern_id) on delete restrict
);

create table public.publication_changes (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_id uuid not null references public.scam_patterns (id) on delete restrict,
    action text not null check (action in ('publish', 'unpublish')),
    pattern_revision_id uuid,
    requested_by uuid not null references public.admin_users (user_id) on delete restrict,
    review_event_id uuid references public.review_events (id) on delete restrict,
    applied_release_id uuid references public.public_releases (id) on delete restrict,
    reason text not null check (btrim(reason) <> ''),
    created_at timestamptz not null default now(),
    constraint publication_changes_revision_pattern_fk foreign key (pattern_revision_id, pattern_id)
        references public.pattern_revisions (id, pattern_id) on delete restrict,
    constraint publication_changes_action_shape check (
        (action = 'publish' and pattern_revision_id is not null)
        or (action = 'unpublish' and pattern_revision_id is null)
    )
);

create table public.operation_leases (
    lease_key text primary key check (btrim(lease_key) <> ''),
    holder_id text not null check (btrim(holder_id) <> ''),
    acquired_at timestamptz not null default now(),
    expires_at timestamptz not null,
    constraint operation_leases_time_order check (expires_at > acquired_at)
);

create index source_items_canonical_url_idx on public.source_items (canonical_url);
create index source_items_last_seen_idx on public.source_items (last_seen_at desc);
create index source_item_versions_content_hash_idx on public.source_item_versions (content_hash);
create index source_item_versions_origin_group_idx on public.source_item_versions (origin_group_key);
create index source_item_versions_processing_idx on public.source_item_versions (processing_status, fetched_at);
create index ai_artifacts_status_stage_idx on public.ai_artifacts (status, stage, created_at);
create index scam_patterns_lifecycle_idx on public.scam_patterns (lifecycle_status, last_seen_at desc);
create index pattern_revisions_status_idx on public.pattern_revisions (revision_status, approved_at desc);
create index scam_aliases_normalized_idx on public.scam_aliases (normalized_alias);
create index pattern_evidence_family_idx on public.pattern_evidence (pattern_id, evidence_family_id);
create index pattern_evidence_recheck_idx on public.pattern_evidence (recheck_due_at) where acceptance_status = 'accepted';
create index evidence_claim_support_revision_idx on public.evidence_claim_support (pattern_revision_id, field_path);
create unique index review_items_open_dedupe_unique
    on public.review_items (dedupe_key)
    where status in ('pending', 'in_review', 'needs_evidence');
create index review_items_queue_idx on public.review_items (status, priority desc, created_at);
create index pipeline_runs_started_idx on public.pipeline_runs (started_at desc);
create index source_run_results_source_idx on public.source_run_results (source_id, created_at desc);
create index review_events_target_idx on public.review_events (target_type, target_id, created_at);
create index heat_snapshots_pattern_as_of_idx on public.heat_snapshots (pattern_id, as_of desc, calculated_at desc);
create index public_releases_state_no_idx on public.public_releases (state, release_no desc);
create index publication_changes_pending_idx on public.publication_changes (created_at, id) where applied_release_id is null;

commit;
