\set ON_ERROR_STOP on
begin;
select set_config('request.jwt.claims', '{"role":"service_role"}', true);
select set_config('request.jwt.claim.role', 'service_role', true);

do $$
declare
    v_run uuid;
    v_version uuid;
    v_claim jsonb;
    v_repeat jsonb;
    v_draft jsonb;
    v_values jsonb;
    v_spans jsonb;
    v_text text;
    v_heat jsonb;
    v_payload jsonb := '{"synthetic":true,"reason":"local_contract"}'::jsonb;
begin
    update public.sources set enabled = true, collection_allowed = true,
        reviewed_at = date '2026-09-20'
    where source_key = 'fixture-police-alerts';
    v_draft := '{
      "canonical_name":"合成补贴来电骗局",
      "short_name":"合成补贴来电骗局",
      "one_sentence_summary":"合成来电索取验证码并要求转账",
      "pattern_type":"impersonation",
      "legal_status":"reported_case",
      "contact_channels":["phone_call"],
      "hooks":["养老补贴"],
      "requested_actions":["索取验证码"],
      "warning_signs":["索取验证码"],
      "what_to_do":["挂断并拨打官方电话核实"],
      "last_material_change_at":"2026-09-18T00:00:00Z"
    }'::jsonb;
    v_values := jsonb_build_object(
        'canonical_name','合成补贴来电骗局',
        'short_name','合成补贴来电骗局',
        'one_sentence_summary','合成来电索取验证码并要求转账',
        'pattern_type','impersonation',
        'legal_status','reported_case',
        'risk_type','confirmed_scam',
        'public_evidence_label','警方通报的诈骗案件',
        'contact_channels[1]','phone_call',
        'hooks[1]','养老补贴',
        'warning_signs[1]','索取验证码',
        'requested_actions[1]','索取验证码',
        'what_to_do[1]','挂断并拨打官方电话核实',
        'first_seen_at','2026-09-18T00:00:00.000000Z',
        'last_seen_at','2026-09-18T00:00:00.000000Z',
        'last_material_change_at','2026-09-18T00:00:00.000000Z'
    );
    select string_agg(value, ' | ' order by key) into v_text
    from jsonb_each_text(v_values);
    select jsonb_agg(jsonb_build_object(
        'field_path', key,
        'claim_value', value,
        'start', strpos(v_text, value) - 1,
        'end', strpos(v_text, value) - 1 + char_length(value),
        'excerpt', value
    ) order by key) into v_spans from jsonb_each_text(v_values);
    v_heat := jsonb_build_object('version','scam-heat-v0.1',
        'as_of','2026-09-20','score',50,'inputs_hash',repeat('b',64),
        'components','{"target_relevance":30,"freshness":20,"harm":0,"spread":0,"novelty":0}'::jsonb);
    v_run := public.start_pipeline_run(
        'manual',repeat('a',40),repeat('b',64),repeat('c',64),'pipeline-v0.1');
    v_version := public.ingest_source_version(
        'fixture-police-alerts','candidate-contract',
        'https://alerts.example.invalid/notices/candidate-contract',
        'Synthetic candidate',v_text,
        encode(extensions.digest(convert_to('Synthetic candidate' || E'\n' || v_text,'UTF8'),'sha256'),'hex'),
        '2026-09-18 00:00:00+00');
    if (public.claim_source_version('fixture-police-alerts',v_run::text,300)->>'version_id')::uuid
       <> v_version then raise exception 'candidate_not_claimed'; end if;
    begin
        perform public.submit_new_pattern_candidate(v_version,'other-holder',v_run,
            v_draft,v_spans,v_heat,v_payload,array['local_contract']);
        raise exception 'foreign_claim_accepted';
    exception when insufficient_privilege then
        if sqlerrm <> 'candidate_claim_invalid' then raise; end if;
    end;
    begin
        perform public.submit_new_pattern_candidate(v_version,v_run::text,v_run,
            v_draft,jsonb_set(v_spans,'{0,start}','9999'::jsonb),v_heat,v_payload,
            array['local_contract']);
        raise exception 'fabricated_span_accepted';
    exception when check_violation then
        if sqlerrm <> 'candidate_span_mismatch' then raise; end if;
    end;
    v_claim := public.submit_new_pattern_candidate(v_version,v_run::text,v_run,
        v_draft,v_spans,v_heat,v_payload,array['local_contract']);
    if v_claim->>'lifecycle_status' <> 'review_ready'
       or (v_claim->>'missing_claim_count')::integer <> 0 then
        raise exception 'complete_claims_not_review_ready: %', v_claim;
    end if;
    v_repeat := public.submit_new_pattern_candidate(v_version,v_run::text,v_run,
        v_draft,v_spans,v_heat,v_payload,array['local_contract']);
    if v_repeat->>'pattern_id' <> v_claim->>'pattern_id'
       or v_repeat->>'replayed' <> 'true' then
        raise exception 'candidate_replay_not_idempotent';
    end if;
    begin
        perform public.submit_new_pattern_candidate(v_version,v_run::text,v_run,
            v_draft,v_spans,v_heat,'{"synthetic":true,"changed":true}'::jsonb,
            array['local_contract']);
        raise exception 'changed_replay_accepted';
    exception when check_violation then
        if sqlerrm <> 'candidate_replay_mismatch' then raise; end if;
    end;
    if (select count(*) from public.source_version_candidates where source_item_version_id=v_version) <> 1
       or (select count(*) from public.pattern_evidence where pattern_id=(v_claim->>'pattern_id')::uuid) <> 1
       or (select count(*) from public.evidence_claim_support where pattern_revision_id=(v_claim->>'revision_id')::uuid) <> 15
       or exists(select 1 from public.pattern_revisions where id=(v_claim->>'revision_id')::uuid and revision_status <> 'draft')
    then
        raise exception 'candidate_transaction_incomplete';
    end if;
    if has_function_privilege('authenticated',
        'public.submit_new_pattern_candidate(uuid,text,uuid,jsonb,jsonb,jsonb,jsonb,text[])',
        'execute') then raise exception 'candidate_rpc_human_grant'; end if;
    if jsonb_typeof(public.list_pattern_match_candidates('impersonation', 3)) <> 'array'
       or jsonb_array_length(public.list_pattern_match_candidates('impersonation', 3)) > 3
       or has_function_privilege('authenticated',
           'public.list_pattern_match_candidates(text,integer)', 'execute')
    then raise exception 'match_candidate_boundary_failed'; end if;
    begin
        perform public.list_pattern_match_candidates('impersonation', 11);
        raise exception 'unbounded_match_candidates_accepted';
    exception when check_violation then
        if sqlerrm <> 'match_candidate_request_invalid' then raise; end if;
    end;
    raise notice 'candidate red/green: foreign claim, fabricated span and changed replay rejected; exact evidence, one draft, one review passed';
end;
$$;
rollback;
\echo 'Local transactional candidate intake passed.'
