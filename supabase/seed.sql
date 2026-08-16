-- Synthetic, non-production fixtures only. The reserved .invalid domain cannot resolve.
-- No approved revision is seeded: approval must be exercised with an authenticated
-- local reviewer so the same identity trigger used in production is tested.

insert into public.sources (
    id,
    source_key,
    name,
    domain,
    publisher_group,
    source_type,
    authority_tier,
    ingestion_method,
    entry_url,
    enabled,
    poll_frequency,
    parser_config,
    config_hash,
    created_at,
    synced_at
) values (
    '10000000-0000-4000-8000-000000000001',
    'fixture-police-alerts',
    '虚构市公安提醒（测试）',
    'alerts.example.invalid',
    'fixture-police',
    'police',
    'A1',
    'rss',
    'https://alerts.example.invalid/feed.xml',
    false,
    'manual',
    '{"schema_version":"source-parser-v1","fixture":"synthetic"}'::jsonb,
    repeat('a', 64),
    '2026-08-16 00:00:00+00',
    '2026-08-16 00:00:00+00'
);

insert into public.source_items (
    id,
    source_id,
    external_id,
    identity_key,
    canonical_url,
    first_seen_at,
    last_seen_at,
    created_at,
    updated_at
) values (
    '20000000-0000-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000001',
    'fixture-alert-001',
    'fixture-alert-001',
    'https://alerts.example.invalid/notices/fixture-alert-001',
    '2026-08-15 08:00:00+00',
    '2026-08-15 08:00:00+00',
    '2026-08-15 08:00:00+00',
    '2026-08-15 08:00:00+00'
);

insert into public.source_item_versions (
    id,
    source_item_id,
    url,
    canonical_url,
    title,
    author,
    language,
    published_at,
    fetched_at,
    clean_text,
    text_truncated,
    content_hash,
    raw_html_hash,
    origin_group_key,
    processing_status,
    attempt_count,
    created_at
) values (
    '30000000-0000-4000-8000-000000000001',
    '20000000-0000-4000-8000-000000000001',
    'https://alerts.example.invalid/notices/fixture-alert-001',
    'https://alerts.example.invalid/notices/fixture-alert-001',
    '警惕虚构养老补贴代办来电',
    '虚构市公安宣传处',
    'zh-CN',
    '2026-08-14 01:00:00+00',
    '2026-08-15 08:00:00+00',
    '测试材料：来电者冒充社区工作人员，以代办养老补贴为由索取验证码并要求转账。警方提醒不要提供验证码，先挂断并拨打官方电话核实。',
    false,
    repeat('b', 64),
    repeat('c', 64),
    'fixture-origin-001',
    'processed',
    1,
    '2026-08-15 08:00:00+00'
);

update public.source_items
set current_version_id = '30000000-0000-4000-8000-000000000001'
where id = '20000000-0000-4000-8000-000000000001';

insert into public.ai_artifacts (
    id,
    source_item_version_id,
    stage,
    provider,
    model,
    prompt_version,
    schema_version,
    input_hash,
    status,
    result,
    usage,
    latency_ms,
    created_at
) values (
    '40000000-0000-4000-8000-000000000001',
    '30000000-0000-4000-8000-000000000001',
    'relevance',
    'recorded',
    'fixture-model',
    'relevance-v1',
    'relevance-result-v1',
    repeat('d', 64),
    'success',
    '{"relevant":true,"elderly_relevance":"high","category":"impersonation_scam","confidence":0.94,"reason_code":"fixture_elderly_impersonation"}'::jsonb,
    '{"input_tokens":0,"output_tokens":0,"recorded":true}'::jsonb,
    0,
    '2026-08-15 08:00:01+00'
);

insert into public.scam_patterns (
    id,
    slug,
    lifecycle_status,
    first_seen_at,
    last_seen_at,
    row_version,
    created_at,
    updated_at
) values (
    '50000000-0000-4000-8000-000000000001',
    'fixture-pension-subsidy-call',
    'review_ready',
    '2026-08-14 01:00:00+00',
    '2026-08-14 01:00:00+00',
    1,
    '2026-08-15 08:00:02+00',
    '2026-08-15 08:00:02+00'
);

insert into public.pattern_revisions (
    id,
    pattern_id,
    revision_no,
    schema_version,
    revision_status,
    canonical_name,
    short_name,
    pattern_type,
    risk_type,
    evidence_level,
    legal_status,
    public_evidence_label,
    one_sentence_summary,
    target_population,
    contact_channels,
    impersonated_identities,
    hooks,
    common_phrases,
    pressure_tactics,
    requested_actions,
    money_paths,
    technology_used,
    warning_signs,
    what_to_do,
    regions,
    first_seen_at,
    last_seen_at,
    last_material_change_at,
    evidence_set_hash,
    content_hash,
    created_at
) values (
    '60000000-0000-4000-8000-000000000001',
    '50000000-0000-4000-8000-000000000001',
    1,
    'pattern-revision-v1',
    'draft',
    '冒充社区代办养老补贴',
    '养老补贴代办骗局',
    'impersonation',
    'confirmed_scam',
    'A',
    'reported_case',
    '警方通报的诈骗案件',
    '来电者冒充社区工作人员，以代办补贴为由索取验证码或要求转账。',
    array['older_adults'],
    array['phone_call'],
    array['community_worker'],
    array['pension_subsidy'],
    array['代办补贴'],
    array['limited_time'],
    array['share_verification_code', 'transfer_money'],
    array['bank_transfer'],
    array['caller_id_spoofing'],
    array['索取短信验证码', '要求先交手续费'],
    array['立即挂断', '通过官方电话核实'],
    array['CN-XX'],
    '2026-08-14 01:00:00+00',
    '2026-08-14 01:00:00+00',
    '2026-08-14 01:00:00+00',
    repeat('e', 64),
    repeat('f', 64),
    '2026-08-15 08:00:02+00'
);

update public.scam_patterns
set current_draft_revision_id = '60000000-0000-4000-8000-000000000001'
where id = '50000000-0000-4000-8000-000000000001';

insert into public.scam_aliases (
    id,
    pattern_revision_id,
    alias,
    normalized_alias,
    alias_type,
    created_at
) values (
    '61000000-0000-4000-8000-000000000001',
    '60000000-0000-4000-8000-000000000001',
    '社区补贴代办',
    '社区补贴代办',
    'search',
    '2026-08-15 08:00:02+00'
);

insert into public.pattern_evidence (
    id,
    pattern_id,
    source_item_version_id,
    evidence_type,
    origin_group_key,
    evidence_family_id,
    claim_summary,
    event_date,
    region,
    new_tactic,
    is_material_update,
    acceptance_status,
    last_verified_at,
    recheck_due_at,
    source_status,
    created_at
) values (
    '70000000-0000-4000-8000-000000000001',
    '50000000-0000-4000-8000-000000000001',
    '30000000-0000-4000-8000-000000000001',
    'official_notice',
    'fixture-origin-001',
    'd0000000-0000-4000-8000-000000000001',
    '虚构警方材料描述了冒充社区人员索取验证码和转账的做法。',
    '2026-08-14',
    'CN-XX',
    true,
    true,
    'proposed',
    '2026-08-15 08:00:00+00',
    '2026-09-14 08:00:00+00',
    'available',
    '2026-08-15 08:00:03+00'
);

insert into public.evidence_spans (
    id,
    pattern_evidence_id,
    start_offset,
    end_offset,
    excerpt,
    excerpt_hash,
    created_at
) values (
    '80000000-0000-4000-8000-000000000001',
    '70000000-0000-4000-8000-000000000001',
    5,
    43,
    '来电者冒充社区工作人员，以代办养老补贴为由索取验证码并要求转账。',
    repeat('8', 64),
    '2026-08-15 08:00:03+00'
);

insert into public.evidence_claim_support (
    pattern_revision_id,
    field_path,
    value_hash,
    pattern_evidence_id,
    evidence_span_id,
    created_at
) values (
    '60000000-0000-4000-8000-000000000001',
    'one_sentence_summary',
    encode(extensions.digest(convert_to('来电者冒充社区工作人员，以代办补贴为由索取验证码或要求转账。', 'UTF8'), 'sha256'), 'hex'),
    '70000000-0000-4000-8000-000000000001',
    '80000000-0000-4000-8000-000000000001',
    '2026-08-15 08:00:03+00'
);

insert into public.heat_snapshots (
    id,
    pattern_id,
    score_version,
    as_of,
    score,
    breakdown,
    input_hash,
    calculated_at
) values (
    '90000000-0000-4000-8000-000000000001',
    '50000000-0000-4000-8000-000000000001',
    'scam-heat-v0.1',
    '2026-08-16',
    78,
    '{"target_relevance":{"value":"older_adults","points":30},"freshness":{"value":"days_0_3","points":20},"harm":{"value":"moderate_loss","points":10},"spread":{"value":"single_case","points":3},"novelty":{"value":"new_mechanism","points":15},"total":78}'::jsonb,
    repeat('1', 64),
    '2026-08-16 00:00:00+00'
);

insert into public.review_items (
    id,
    review_type,
    target_id,
    status,
    priority,
    heat_at_creation,
    evidence_level_at_creation,
    reason_codes,
    candidate_schema_version,
    candidate_payload,
    candidate_hash,
    base_row_version,
    dedupe_key,
    created_at,
    updated_at
) values (
    'a0000000-0000-4000-8000-000000000001',
    'new_pattern',
    '50000000-0000-4000-8000-000000000001',
    'pending',
    80,
    78,
    'A',
    array['eligible_for_review', 'new_a_level_pattern'],
    'review-candidate-v1',
    '{"fixture":true,"proposed_name":"冒充社区代办养老补贴","gate_outcome":"eligible_for_review","why_now":"出现了针对老年人的新冒充话术"}'::jsonb,
    repeat('2', 64),
    1,
    'fixture:new-pattern:pension-subsidy-call:v1',
    '2026-08-16 00:00:00+00',
    '2026-08-16 00:00:00+00'
);

insert into public.pipeline_runs (
    id,
    github_run_id,
    github_run_attempt,
    trigger,
    commit_sha,
    registry_hash,
    pipeline_version,
    behavior_hash,
    discovered_count,
    relevant_count,
    review_count,
    started_at,
    finished_at,
    outcome
) values (
    'b0000000-0000-4000-8000-000000000001',
    'fixture-run-001',
    1,
    'fixture',
    repeat('0', 40),
    repeat('3', 64),
    'pipeline-v0.1',
    repeat('4', 64),
    1,
    1,
    1,
    '2026-08-15 08:00:00+00',
    '2026-08-15 08:00:04+00',
    'success'
);

insert into public.source_states (
    source_id,
    cursor_value,
    last_attempt_at,
    last_success_at,
    consecutive_failures,
    updated_at
) values (
    '10000000-0000-4000-8000-000000000001',
    'fixture-alert-001',
    '2026-08-15 08:00:04+00',
    '2026-08-15 08:00:04+00',
    0,
    '2026-08-15 08:00:04+00'
);

insert into public.source_run_results (
    id,
    pipeline_run_id,
    source_id,
    outcome,
    duration_ms,
    discovered_count,
    fetched_count,
    inserted_count,
    retry_count,
    created_at
) values (
    'c0000000-0000-4000-8000-000000000001',
    'b0000000-0000-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000001',
    'success',
    4000,
    1,
    1,
    1,
    0,
    '2026-08-15 08:00:04+00'
);
