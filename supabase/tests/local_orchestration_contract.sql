\set ON_ERROR_STOP on
begin;
select set_config('request.jwt.claims', '{"role":"service_role"}', true);
select set_config('request.jwt.claim.role', 'service_role', true);

do $$
declare
    v_source_id uuid;
    run_id uuid;
    version_id uuid;
    first_claim jsonb;
    retry_claim jsonb;
begin
    begin
        perform public.sync_registry_source(
            'fixture-police-alerts', '虚构市公安提醒（测试）', 'alerts.example.invalid',
            'fixture-police', 'police', 'A1', 'rss',
            'https://alerts.example.invalid/feed.xml', true, false, null, 'manual',
            '{"schema_version":"source-parser-v1","fixture":"synthetic"}',
            repeat('a', 64)
        );
        raise exception 'unreviewed_source_enabled';
    exception when check_violation then
        if sqlerrm <> 'source_review_or_config_invalid' then raise; end if;
    end;

    v_source_id := public.sync_registry_source(
        'fixture-police-alerts', '虚构市公安提醒（测试）', 'alerts.example.invalid',
        'fixture-police', 'police', 'A1', 'rss',
        'https://alerts.example.invalid/feed.xml', true, true, date '2026-09-20',
        'manual', '{"schema_version":"source-parser-v1","fixture":"synthetic"}',
        repeat('a', 64)
    );
    if v_source_id <> '10000000-0000-4000-8000-000000000001' then
        raise exception 'registry_sync_changed_source_identity';
    end if;
    begin
        perform public.sync_registry_source(
            'fixture-police-alerts', '虚构市公安提醒（测试）', 'alerts.example.invalid',
            'fixture-police', 'media', 'A1', 'rss',
            'https://alerts.example.invalid/feed.xml', true, true, date '2026-09-20',
            'manual', '{"schema_version":"source-parser-v1","fixture":"synthetic"}',
            repeat('a', 64)
        );
        raise exception 'source_identity_reclassified_silently';
    exception when check_violation then
        if sqlerrm <> 'source_identity_changed' then raise; end if;
    end;

    run_id := public.start_pipeline_run(
        'manual', repeat('a', 40), repeat('b', 64), repeat('c', 64), 'pipeline-v0.1'
    );
    if not public.acquire_operation_lease('source:fixture-police-alerts', run_id::text, 300)
       or public.acquire_operation_lease('source:fixture-police-alerts', 'other-holder', 300)
       or public.release_operation_lease('source:fixture-police-alerts', 'other-holder')
    then
        raise exception 'operation_lease_owner_boundary_failed';
    end if;
    if not public.release_operation_lease('source:fixture-police-alerts', run_id::text) then
        raise exception 'operation_lease_release_failed';
    end if;

    version_id := public.ingest_source_version(
        'fixture-police-alerts', 'orchestration-item',
        'https://alerts.example.invalid/notices/orchestration-item',
        'Synthetic orchestration title', 'Synthetic orchestration body',
        encode(extensions.digest('Synthetic orchestration title' || E'\n' ||
            'Synthetic orchestration body', 'sha256'), 'hex'), null
    );
    first_claim := public.claim_source_version('fixture-police-alerts', run_id::text, 300);
    if first_claim #>> '{version_id}' <> version_id::text
       or public.claim_source_version('fixture-police-alerts', 'other-holder', 300) is not null
    then
        raise exception 'pending_claim_not_exclusive';
    end if;
    begin
        perform public.finish_source_version(version_id, 'other-holder', 'processed');
        raise exception 'foreign_claim_completed';
    exception when insufficient_privilege then
        if sqlerrm <> 'source_claim_not_owned' then raise; end if;
    end;
    perform public.finish_source_version(version_id, run_id::text, 'error', 'model_timeout');
    retry_claim := public.claim_source_version('fixture-police-alerts', run_id::text, 300);
    if retry_claim #>> '{version_id}' <> version_id::text then
        raise exception 'failed_item_not_resumable';
    end if;
    perform public.finish_source_version(version_id, run_id::text, 'processed');
    begin
        update public.source_item_versions set clean_text = 'Tampered body'
        where id = version_id;
        raise exception 'processed_content_mutation_accepted';
    exception when sqlstate '55000' then
        if sqlerrm <> 'source_item_version_content_is_immutable' then raise; end if;
    end;
    if public.claim_source_version('fixture-police-alerts', run_id::text, 300) is not null then
        raise exception 'processed_item_reclaimed';
    end if;

    -- Simulate a worker process disappearing while it owns a claim. The next
    -- process may resume only after expiry; the old holder loses completion rights.
    version_id := public.ingest_source_version(
        'fixture-police-alerts', 'interrupted-process-item',
        'https://alerts.example.invalid/notices/interrupted-process-item',
        'Synthetic interrupted title', 'Synthetic interrupted body',
        encode(extensions.digest('Synthetic interrupted title' || E'\n' ||
            'Synthetic interrupted body', 'sha256'), 'hex'), null
    );
    first_claim := public.claim_source_version('fixture-police-alerts', 'stopped-process', 300);
    if first_claim #>> '{version_id}' <> version_id::text then
        raise exception 'interrupted_process_claim_missing';
    end if;
    update public.source_item_versions
    set claimed_until = now() - interval '1 second'
    where id = version_id;
    retry_claim := public.claim_source_version('fixture-police-alerts', 'replacement-process', 300);
    if retry_claim #>> '{version_id}' <> version_id::text then
        raise exception 'interrupted_process_not_reclaimed';
    end if;
    begin
        perform public.finish_source_version(version_id, 'stopped-process', 'processed');
        raise exception 'interrupted_holder_completed_after_takeover';
    exception when insufficient_privilege then
        if sqlerrm <> 'source_claim_not_owned' then raise; end if;
    end;
    perform public.finish_source_version(version_id, 'replacement-process', 'processed');
    if public.claim_source_version('fixture-police-alerts', 'replacement-process', 300) is not null then
        raise exception 'interrupted_process_created_duplicate_claim';
    end if;

    version_id := public.ingest_source_version(
        'fixture-police-alerts', 'irrelevant-retention-item',
        'https://alerts.example.invalid/notices/irrelevant-retention-item',
        'Synthetic unrelated title', 'Synthetic unrelated body',
        encode(extensions.digest('Synthetic unrelated title' || E'\n' ||
            'Synthetic unrelated body', 'sha256'), 'hex'), null
    );
    first_claim := public.claim_source_version('fixture-police-alerts', run_id::text, 300);
    if first_claim #>> '{version_id}' <> version_id::text
       or first_claim #>> '{clean_text}' <> 'Synthetic unrelated body' then
        raise exception 'irrelevant_version_not_classifiable';
    end if;
    perform public.finish_source_version(version_id, run_id::text, 'irrelevant');
    if exists(select 1 from public.source_item_versions
              where id = version_id and clean_text is not null)
       or public.claim_source_version('fixture-police-alerts', run_id::text, 300) is not null
    then
        raise exception 'irrelevant_text_retained_or_reclaimed';
    end if;

    perform public.record_source_checkpoint(
        'fixture-police-alerts', run_id, false, null, null, null, 'source_timeout'
    );
    if (select cursor_value from public.source_states where source_id = v_source_id)
       <> 'fixture-alert-001' then
        raise exception 'failure_advanced_cursor';
    end if;
    perform public.record_source_checkpoint(
        'fixture-police-alerts', run_id, true, 'cursor-001', 'etag-001', null, null
    );
    if not exists(
        select 1 from public.source_states
        where source_states.source_id = v_source_id
          and cursor_value = 'cursor-001' and consecutive_failures = 0
    ) then
        raise exception 'successful_checkpoint_missing';
    end if;
    perform public.finish_pipeline_run(run_id, 'success', 1, 1, 0);
    perform public.finish_pipeline_run(run_id, 'success', 1, 1, 0);
    begin
        perform public.finish_pipeline_run(run_id, 'failed', 1, 1, 0, 'conflict');
        raise exception 'run_replay_mismatch_accepted';
    exception when check_violation then
        if sqlerrm <> 'pipeline_run_replay_mismatch' then raise; end if;
    end;
    if has_function_privilege('authenticated',
        'public.claim_source_version(text,text,integer)', 'execute')
       or has_function_privilege('anon',
        'public.sync_registry_source(text,text,text,text,text,text,text,text,boolean,boolean,date,text,jsonb,text)',
        'execute')
    then
        raise exception 'worker_orchestration_grants_invalid';
    end if;
    raise notice 'orchestration red/green: unreviewed source, foreign claim and replay rejected; retry, irrelevant-text purge, cursor and lease passed';
end;
$$;
rollback;
\echo 'Local durable orchestration contract passed.'
