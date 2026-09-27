\set ON_ERROR_STOP on
begin;
select set_config('request.jwt.claims', '{"role":"service_role"}', true);
select set_config('request.jwt.claim.role', 'service_role', true);

do $$
declare
    v_source_key text;
    v_pattern public.scam_patterns%rowtype;
    v_base public.pattern_revisions%rowtype;
    v_run uuid;
    v_version uuid;
    v_claim jsonb;
    v_deferred_version uuid;
    v_deferred_claim jsonb;
    v_receipt jsonb;
    v_replay jsonb;
    v_expected_evidence_hash text;
    v_expected_content_hash text;
    v_text text := '合成来电索取验证码并要求转账。本地追加案例，仅供测试。';
    v_heat jsonb := jsonb_build_object(
        'version','scam-heat-v0.1','as_of',current_date::text,
        'score',50,'inputs_hash',repeat('b',64),
        'components','{"target_relevance":30,"freshness":20,"harm":0,"spread":0,"novelty":0}'::jsonb,
        'feature_values','{}'::jsonb
    );
    v_match jsonb := '{"same_pattern":true,"confidence":0.95,"material_change":false,"reason_codes":["same_mechanism"],"changes":[]}'::jsonb;
begin
    select pattern.* into v_pattern
    from public.scam_patterns as pattern
    join public.source_version_candidates as candidate on candidate.pattern_id = pattern.id
    join public.source_item_versions as version on version.id = candidate.source_item_version_id
    join public.source_items as item on item.id = version.source_item_id
    join public.sources as source on source.id = item.source_id
    where pattern.latest_approved_revision_id is not null
      and source.enabled and source.collection_allowed
    order by pattern.created_at desc limit 1;
    if v_pattern.id is null then raise exception 'approved_local_pattern_required'; end if;
    select source.source_key into v_source_key
    from public.source_version_candidates as candidate
    join public.source_item_versions as version on version.id = candidate.source_item_version_id
    join public.source_items as item on item.id = version.source_item_id
    join public.sources as source on source.id = item.source_id
    where candidate.pattern_id = v_pattern.id;
    select * into v_base from public.pattern_revisions
    where id = v_pattern.latest_approved_revision_id;
    if not exists(select 1 from jsonb_array_elements(
        public.list_pattern_match_candidates(v_base.pattern_type,10)) as candidate
        where candidate->>'pattern_id' = v_pattern.id::text) then
        raise exception 'approved_pattern_not_matchable';
    end if;
    v_run := public.start_pipeline_run(
        'manual',repeat('a',40),repeat('b',64),repeat('c',64),'pipeline-v0.1');
    v_version := public.ingest_source_version(
        v_source_key,'existing-pattern-update-contract',
        'https://alerts.example.invalid/notices/existing-pattern-update-contract',
        '合成来电追加案例',v_text,
        encode(extensions.digest(convert_to('合成来电追加案例' || E'\n' || v_text,
            'UTF8'),'sha256'),'hex'),current_date::timestamptz);
    v_claim := public.claim_source_version(v_source_key,v_run::text,300);
    if v_claim->>'version_id' <> v_version::text then
        raise exception 'existing_version_claim_failed';
    end if;
    begin
        perform public.submit_existing_pattern_evidence(
            v_version,'foreign-holder',v_run,v_pattern.id,v_base.id,
            '合成来电索取验证码并要求转账',v_match,v_heat,
            '{"synthetic":true}'::jsonb,array['routine_case_review']);
        raise exception 'foreign_existing_claim_accepted';
    exception when insufficient_privilege then
        if sqlerrm <> 'existing_candidate_claim_invalid' then raise; end if;
    end;
    begin
        perform public.submit_existing_pattern_evidence(
            v_version,v_run::text,v_run,v_pattern.id,v_base.id,
            '合成来电索取验证码并要求转账',
            jsonb_set(v_match,'{same_pattern}','false'::jsonb),v_heat,
            '{"synthetic":true}'::jsonb,array['routine_case_review']);
        raise exception 'false_existing_match_accepted';
    exception when check_violation then
        if sqlerrm <> 'existing_candidate_shape_invalid' then raise; end if;
    end;
    v_receipt := public.submit_existing_pattern_evidence(
        v_version,v_run::text,v_run,v_pattern.id,v_base.id,
        '合成来电索取验证码并要求转账',v_match,v_heat,
        '{"synthetic":true}'::jsonb,array['routine_case_review']);
    v_replay := public.submit_existing_pattern_evidence(
        v_version,v_run::text,v_run,v_pattern.id,v_base.id,
        '合成来电索取验证码并要求转账',v_match,v_heat,
        '{"synthetic":true}'::jsonb,array['routine_case_review']);
    select encode(extensions.digest(convert_to(coalesce(string_agg(
        evidence.id::text || ':' || version.content_hash || ':' ||
        evidence.origin_group_key || ':' || evidence.evidence_family_id::text || ':' ||
        evidence.evidence_type, '|' order by evidence.id),''),'UTF8'),'sha256'),'hex')
    into v_expected_evidence_hash
    from public.pattern_evidence as evidence
    join public.source_item_versions as version
      on version.id = evidence.source_item_version_id
    where evidence.pattern_id = v_pattern.id
      and (evidence.acceptance_status = 'accepted'
           or evidence.id = (v_receipt->>'evidence_id')::uuid);
    v_expected_content_hash := encode(extensions.digest(convert_to(
        v_base.content_hash || ':' || greatest(v_base.last_seen_at,
        current_date::timestamptz)::text || ':' ||
        coalesce(v_base.last_material_change_at::text,''),'UTF8'),'sha256'),'hex');
    if v_replay->>'replayed' <> 'true'
       or v_replay->>'revision_id' <> v_receipt->>'revision_id'
       or v_receipt->>'pattern_id' <> v_pattern.id::text
       or (select count(*) from public.pattern_evidence
           where pattern_id = v_pattern.id and source_item_version_id = v_version) <> 1
       or (select count(*) from public.evidence_claim_support
           where pattern_revision_id = (v_receipt->>'revision_id')::uuid)
          <> (select count(*) from public.evidence_claim_support
              where pattern_revision_id = v_base.id)
       or (select evidence_set_hash from public.pattern_revisions
           where id = (v_receipt->>'revision_id')::uuid) <> v_expected_evidence_hash
       or (select content_hash from public.pattern_revisions
           where id = (v_receipt->>'revision_id')::uuid) <> v_expected_content_hash
       or (select last_seen_at from public.pattern_revisions
           where id = (v_receipt->>'revision_id')::uuid)
          <> greatest(v_base.last_seen_at,current_date::timestamptz)
       or (select last_material_change_at from public.pattern_revisions
           where id = (v_receipt->>'revision_id')::uuid)
          is distinct from v_base.last_material_change_at
       or (select evidence_set_hash from public.pattern_revisions
           where id = v_base.id) <> v_base.evidence_set_hash
       or (select content_hash from public.pattern_revisions
           where id = v_base.id) <> v_base.content_hash
       or (select review_type from public.review_items
           where id = (v_receipt->>'review_item_id')::uuid) <> 'pattern_update'
    then raise exception 'existing_update_transaction_incomplete'; end if;
    if has_function_privilege('authenticated',
        'public.submit_existing_pattern_evidence(uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[])',
        'execute') then raise exception 'human_can_submit_existing_evidence'; end if;
    v_deferred_version := public.ingest_source_version(
        v_source_key,'existing-pattern-deferred-contract',
        'https://alerts.example.invalid/notices/existing-pattern-deferred-contract',
        '合成待审追加案例',v_text,
        encode(extensions.digest(convert_to('合成待审追加案例' || E'\n' || v_text,
            'UTF8'),'sha256'),'hex'),current_date::timestamptz);
    v_deferred_claim := public.claim_source_version(v_source_key,v_run::text,300);
    if v_deferred_claim->>'version_id' <> v_deferred_version::text then
        raise exception 'pending_update_claim_failed';
    end if;
    begin
        perform public.defer_source_version_for_review(
            v_deferred_version,'foreign-holder',v_pattern.id);
        raise exception 'foreign_review_deferral_accepted';
    exception when insufficient_privilege then
        if sqlerrm <> 'review_deferral_invalid' then raise; end if;
    end;
    perform public.defer_source_version_for_review(
        v_deferred_version,v_run::text,v_pattern.id);
    if not exists(select 1 from public.source_item_versions
        where id = v_deferred_version and processing_status = 'pending_ai'
          and attempt_count = 0 and last_error = 'pending_review_conflict'
          and claim_holder is null)
       or has_function_privilege('authenticated',
            'public.defer_source_version_for_review(uuid,text,uuid)','execute')
    then raise exception 'pending_review_deferral_incomplete'; end if;
    raise notice 'existing-pattern red/green: foreign claim and false match rejected; one proposed evidence, copied supported draft, replay, and no-budget pending deferral passed';
end;
$$;
rollback;
\echo 'Local existing-pattern evidence contract passed.'
