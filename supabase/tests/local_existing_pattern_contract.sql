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
    v_capped_version uuid;
    v_deferred_claim jsonb;
    v_receipt jsonb;
    v_replay jsonb;
    v_recovery jsonb;
    v_payload jsonb;
    v_actor uuid;
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
    v_payload := jsonb_build_object(
        'synthetic',true,'matched_pattern_id',v_pattern.id,
        'matched_revision_id',v_base.id,'comparison',v_match,'heat',v_heat);
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
            v_payload,array['routine_case_review']);
        raise exception 'foreign_existing_claim_accepted';
    exception when insufficient_privilege then
        if sqlerrm <> 'existing_candidate_claim_invalid' then raise; end if;
    end;
    begin
        perform public.submit_existing_pattern_evidence(
            v_version,v_run::text,v_run,v_pattern.id,v_base.id,
            '合成来电索取验证码并要求转账',
            jsonb_set(v_match,'{same_pattern}','false'::jsonb),v_heat,
            v_payload,array['routine_case_review']);
        raise exception 'false_existing_match_accepted';
    exception when check_violation then
        if sqlerrm <> 'existing_candidate_shape_invalid' then raise; end if;
    end;
    v_receipt := public.submit_existing_pattern_evidence(
        v_version,v_run::text,v_run,v_pattern.id,v_base.id,
        '合成来电索取验证码并要求转账',v_match,v_heat,
        v_payload,array['routine_case_review']);
    v_replay := public.submit_existing_pattern_evidence(
        v_version,v_run::text,v_run,v_pattern.id,v_base.id,
        '合成来电索取验证码并要求转账',v_match,v_heat,
        v_payload,array['routine_case_review']);
    begin
        perform public.get_existing_update_recovery(v_version,'foreign-holder');
        raise exception 'foreign_existing_recovery_accepted';
    exception when insufficient_privilege then
        if sqlerrm <> 'existing_recovery_claim_invalid' then raise; end if;
    end;
    v_recovery := public.get_existing_update_recovery(v_version,v_run::text);
    begin
        perform public.defer_recovered_update_for_review(v_version,v_run::text);
        raise exception 'unheld_update_was_deferred';
    exception when insufficient_privilege then
        if sqlerrm <> 'existing_hold_deferral_invalid' then raise; end if;
    end;
    begin
        select user_id into v_actor from public.admin_users where enabled limit 1;
        perform set_config('request.jwt.claims',
            jsonb_build_object('role','authenticated','sub',v_actor)::text,true);
        perform set_config('request.jwt.claim.role','authenticated',true);
        perform set_config('request.jwt.claim.sub',v_actor::text,true);
        update public.review_items set status = 'rejected',
            assigned_to = v_actor,
            decision_note = 'synthetic forged terminal state', resolved_at = now()
        where id = (v_receipt->>'review_item_id')::uuid;
        perform set_config('request.jwt.claims','{"role":"service_role"}',true);
        perform set_config('request.jwt.claim.role','service_role',true);
        perform set_config('request.jwt.claim.sub','',true);
        perform public.get_existing_update_recovery(v_version,v_run::text);
        raise exception 'rejection_without_human_event_accepted';
    exception when check_violation then
        if sqlerrm <> 'existing_recovery_rejection_invalid' then raise; end if;
    end;
    begin
        perform public.submit_existing_pattern_evidence(
            v_version,v_run::text,v_run,v_pattern.id,v_base.id,
            '合成来电索取验证码并要求转账',v_match,
            jsonb_set(v_heat,'{as_of}',to_jsonb((current_date - 1)::text)),
            v_payload,array['routine_case_review']);
        raise exception 'changed_heat_replay_accepted';
    exception when check_violation then
        if sqlerrm <> 'existing_candidate_replay_mismatch' then raise; end if;
    end;
    if v_recovery->>'pattern_id' <> v_receipt->>'pattern_id'
       or v_recovery->>'revision_id' <> v_receipt->>'revision_id'
       or v_recovery->>'review_item_id' <> v_receipt->>'review_item_id'
       or v_recovery->>'evidence_id' <> v_receipt->>'evidence_id'
       or v_recovery->>'candidate_hash' <> v_receipt->>'candidate_hash'
       or v_recovery->>'missing_claim_count' <> '0'
       or v_recovery->>'review_status' <> 'pending'
       or v_recovery->>'policy_recordable' <> 'true'
       or v_recovery->>'policy_decision_id' is not null
       or v_recovery->'candidate_payload' <> v_payload
       or v_replay->>'missing_claim_count' <> v_receipt->>'missing_claim_count'
    then raise exception 'existing_recovery_receipt_inconsistent'; end if;
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
        'execute')
       or has_function_privilege('authenticated',
           'public.get_existing_update_recovery(uuid,text)','execute')
       or has_function_privilege('authenticated',
           'public.defer_recovered_update_for_review(uuid,text)','execute')
       or has_function_privilege('service_role',
           'private.submit_existing_pattern_evidence(uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[])',
           'execute')
    then raise exception 'existing_recovery_grants_invalid'; end if;
    update public.source_item_versions set attempt_count = 3,
        claimed_until = now() - interval '1 second'
    where id = v_version;
    v_claim := public.claim_source_version(v_source_key,'recovery-after-cap',300);
    if v_claim->>'version_id' <> v_version::text
       or (select attempt_count from public.source_item_versions where id = v_version) <> 4
    then raise exception 'committed_update_retry_cap_stranded'; end if;
    begin
        perform public.get_existing_update_recovery(v_version,v_run::text);
        raise exception 'expired_original_holder_recovered_update';
    exception when insufficient_privilege then
        if sqlerrm <> 'existing_recovery_claim_invalid' then raise; end if;
    end;
    if (public.get_existing_update_recovery(v_version,'recovery-after-cap')
       ->>'review_item_id') <> v_receipt->>'review_item_id'
    then raise exception 'replacement_holder_receipt_mismatch'; end if;
    v_capped_version := public.ingest_source_version(
        v_source_key,'uncommitted-retry-cap-contract',
        'https://alerts.example.invalid/notices/uncommitted-retry-cap-contract',
        '合成未提交上限案例',v_text,
        encode(extensions.digest(convert_to('合成未提交上限案例' || E'\n' || v_text,
            'UTF8'),'sha256'),'hex'),current_date::timestamptz);
    update public.source_item_versions set attempt_count = 3
    where id = v_capped_version;
    if public.claim_source_version(v_source_key,'recovery-after-cap',300) is not null
    then raise exception 'uncommitted_retry_cap_weakened'; end if;
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
    raise notice 'existing-pattern red/green: foreign claim and changed-heat replay rejected; committed update bypassed old retry cap, uncommitted cap retained, no-budget deferral passed';
end;
$$;
rollback;
\echo 'Local existing-pattern evidence contract passed.'
