\set ON_ERROR_STOP on
begin;
select set_config('request.jwt.claims', '{"role":"service_role"}', true);
select set_config('request.jwt.claim.role', 'service_role', true);
do $$
declare
    first_id uuid;
    repeat_id uuid;
    mirror_id uuid;
    artifact_id uuid;
    repeat_artifact uuid;
begin
    begin
        perform public.ingest_source_version('fixture-police-alerts', 'intake-case', 'https://alerts.example.invalid/intake', 'Synthetic', 'Synthetic text', '31d1dd92d6d67138ad6bd2dafa63542ab2a06db2988e1357c915efc323ffa7b6', now());
        raise exception 'disabled_source_was_accepted';
    exception when check_violation then
        if sqlerrm <> 'source_not_enabled' then raise; end if;
    end;
    update public.sources set enabled = true, collection_allowed = true,
        reviewed_at = date '2026-09-20'
    where source_key = 'fixture-police-alerts';
    first_id := public.ingest_source_version('fixture-police-alerts', 'intake-case', 'https://alerts.example.invalid/intake', 'Synthetic', 'Synthetic text', '31d1dd92d6d67138ad6bd2dafa63542ab2a06db2988e1357c915efc323ffa7b6', now());
    repeat_id := public.ingest_source_version('fixture-police-alerts', 'intake-case', 'https://alerts.example.invalid/intake', 'Synthetic', 'Synthetic text', '31d1dd92d6d67138ad6bd2dafa63542ab2a06db2988e1357c915efc323ffa7b6', now());
    if first_id <> repeat_id then raise exception 'intake_not_idempotent'; end if;
    mirror_id := public.ingest_source_version('fixture-police-alerts', 'intake-mirror', 'https://alerts.example.invalid/mirror', 'Synthetic', 'Synthetic text', '31d1dd92d6d67138ad6bd2dafa63542ab2a06db2988e1357c915efc323ffa7b6', now());
    if not exists(select 1 from public.source_item_versions where id=mirror_id and duplicate_of_version_id=first_id) then raise exception 'mirror_not_linked'; end if;
    artifact_id := public.store_ai_artifact(first_id, 'relevance', 'local', 'protocol-model', 'relevance-v1', 'relevance-v1', repeat('c',64), '{"relevant":true}', '{}');
    repeat_artifact := public.store_ai_artifact(first_id, 'relevance', 'local', 'protocol-model', 'relevance-v1', 'relevance-v1', repeat('c',64), '{"relevant":true}', '{}');
    if artifact_id <> repeat_artifact then raise exception 'artifact_not_idempotent'; end if;
    if public.get_ai_artifact(first_id, 'relevance', 'local', 'protocol-model', 'relevance-v1', 'relevance-v1', repeat('c',64)) <> '{"relevant":true}'::jsonb then raise exception 'artifact_not_resumable'; end if;
    begin
        perform public.ingest_source_version('fixture-police-alerts', 'foreign', 'https://foreign.invalid/intake', 'Synthetic', 'Synthetic text', repeat('d',64), now());
        raise exception 'foreign_destination_accepted';
    exception when check_violation then
        if sqlerrm <> 'invalid_source_payload' then raise; end if;
    end;
    if has_function_privilege('authenticated', 'public.ingest_source_version(text,text,text,text,text,text,timestamptz,boolean)', 'execute')
       or has_function_privilege('anon', 'public.store_ai_artifact(uuid,text,text,text,text,text,text,jsonb,jsonb)', 'execute') then raise exception 'intake_grants_invalid'; end if;
end;
$$;
rollback;
\echo 'Local intake passed: disabled-source rejection, rerun, mirror provenance, AI cache/resume, foreign-source rejection, grants.'
