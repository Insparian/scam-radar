begin;

-- A claimed source version can produce one immutable candidate. This RPC has no
-- authority to accept evidence, approve a revision or publish a release.
create table public.source_version_candidates (
    source_item_version_id uuid primary key references public.source_item_versions(id) on delete restrict,
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    pattern_id uuid not null unique references public.scam_patterns(id) on delete restrict,
    revision_id uuid not null unique references public.pattern_revisions(id) on delete restrict,
    evidence_id uuid not null unique references public.pattern_evidence(id) on delete restrict,
    review_item_id uuid not null unique references public.review_items(id) on delete restrict,
    created_at timestamptz not null default now()
);

alter table public.source_version_candidates enable row level security;
revoke all on public.source_version_candidates from public, anon, authenticated;
grant select on public.source_version_candidates to service_role;

create or replace function public.submit_new_pattern_candidate(
    p_version_id uuid,
    p_holder_id text,
    p_run_id uuid,
    p_draft jsonb,
    p_spans jsonb,
    p_heat jsonb,
    p_candidate_payload jsonb,
    p_reason_codes text[]
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_version public.source_item_versions%rowtype;
    v_source public.sources%rowtype;
    v_existing public.source_version_candidates%rowtype;
    v_pattern_id uuid;
    v_revision_id uuid;
    v_evidence_id uuid;
    v_review_id uuid;
    v_span_id uuid;
    v_claim record;
    v_span jsonb;
    v_start integer;
    v_end integer;
    v_excerpt text;
    v_field text;
    v_value text;
    v_canonical_name text;
    v_summary text;
    v_short_name text;
    v_label text;
    v_legal_status text;
    v_risk_type text;
    v_evidence_type text;
    v_evidence_level text;
    v_seen_at timestamptz;
    v_candidate_hash text;
    v_content_hash text;
    v_evidence_hash text;
    v_family_id uuid;
    v_missing_count integer;
    v_status text;
    v_heat_score integer;
    v_heat_breakdown jsonb;
begin
    perform private.assert_trusted_service();
    if jsonb_typeof(p_draft) <> 'object'
       or jsonb_typeof(p_spans) <> 'array'
       or jsonb_typeof(p_heat) <> 'object'
       or jsonb_typeof(p_candidate_payload) <> 'object'
       or jsonb_array_length(p_spans) > 80
       or octet_length(p_draft::text) > 30000
       or octet_length(p_candidate_payload::text) > 30000
       or array_length(p_reason_codes, 1) > 30
       or p_holder_id !~ '^[a-zA-Z0-9:_-]{1,120}$'
    then
        raise exception using errcode = '23514', message = 'candidate_shape_invalid';
    end if;

    select * into v_version from public.source_item_versions
    where id = p_version_id for update;
    if not found or v_version.processing_status <> 'processing'
       or v_version.claim_holder is distinct from p_holder_id
       or v_version.claimed_until <= now() then
        raise exception using errcode = '42501', message = 'candidate_claim_invalid';
    end if;
    select source.* into v_source
    from public.source_items as item
    join public.sources as source on source.id = item.source_id
    where item.id = v_version.source_item_id;
    if not v_source.enabled or not v_source.collection_allowed
       or v_source.reviewed_at is null
       or not exists(select 1 from public.pipeline_runs where id = p_run_id and outcome = 'running')
    then
        raise exception using errcode = '42501', message = 'candidate_source_or_run_invalid';
    end if;

    v_candidate_hash := encode(extensions.digest(convert_to(jsonb_build_object(
        'draft',p_draft,'spans',p_spans,'heat',p_heat,
        'payload',p_candidate_payload,'reasons',p_reason_codes
    )::text, 'UTF8'), 'sha256'), 'hex');
    select * into v_existing from public.source_version_candidates
    where source_item_version_id = p_version_id;
    if found then
        if v_existing.candidate_hash <> v_candidate_hash then
            raise exception using errcode = '23514', message = 'candidate_replay_mismatch';
        end if;
        return jsonb_build_object('pattern_id', v_existing.pattern_id,
            'revision_id', v_existing.revision_id, 'evidence_id', v_existing.evidence_id,
            'review_item_id', v_existing.review_item_id,
            'candidate_hash', v_candidate_hash, 'replayed', true);
    end if;

    v_canonical_name := btrim(p_draft->>'canonical_name');
    v_short_name := btrim(p_draft->>'short_name');
    v_summary := btrim(p_draft->>'one_sentence_summary');
    v_legal_status := p_draft->>'legal_status';
    if v_canonical_name is null or char_length(v_canonical_name) not between 2 and 120
       or v_short_name is null or char_length(v_short_name) not between 2 and 120
       or v_summary is null or char_length(v_summary) not between 4 and 600
       or p_draft->>'pattern_type' is null
       or v_legal_status not in ('warning','reported_case','enforcement','charge','judgment','unknown')
       or exists (
           select 1 from jsonb_object_keys(p_draft) as key
           where key not in (
             'canonical_name','short_name','one_sentence_summary','pattern_type','legal_status',
             'last_material_change_at',
             'target_population','contact_channels','impersonated_identities',
             'hooks','pressure_tactics','requested_actions','money_paths',
             'technology_used','warning_signs','what_to_do','regions'
           )
       )
       or exists (
           select 1 from jsonb_each(p_draft) as field
           where field.key in (
             'target_population','contact_channels','impersonated_identities',
             'hooks','pressure_tactics','requested_actions','money_paths',
             'technology_used','warning_signs','what_to_do','regions'
           ) and jsonb_typeof(field.value) <> 'array'
       )
    then
        raise exception using errcode = '23514', message = 'candidate_draft_invalid';
    end if;
    if jsonb_array_length(coalesce(p_draft->'contact_channels','[]'::jsonb)) = 0
       or jsonb_array_length(coalesce(p_draft->'warning_signs','[]'::jsonb)) = 0
       or jsonb_array_length(coalesce(p_draft->'what_to_do','[]'::jsonb)) = 0
    then
        raise exception using errcode = '23514', message = 'candidate_public_fields_missing';
    end if;

    if v_source.source_type = 'police' and v_source.authority_tier = 'A1'
       and v_legal_status in ('reported_case','enforcement','charge') then
        v_risk_type := 'confirmed_scam';
        v_label := '警方通报的诈骗案件';
        v_evidence_type := 'official_notice';
        v_evidence_level := 'A';
    elsif v_source.source_type = 'court' and v_source.authority_tier = 'A1'
       and v_legal_status = 'judgment' then
        v_risk_type := 'confirmed_scam';
        v_label := '司法机关已公开裁判';
        v_evidence_type := 'judgment';
        v_evidence_level := 'A';
    elsif v_source.source_type = 'regulator' and v_source.authority_tier in ('A1','A2')
       and v_legal_status in ('warning','enforcement') then
        v_risk_type := 'risk_alert';
        v_label := '监管部门已提示风险';
        v_evidence_type := 'risk_warning';
        v_evidence_level := 'A';
    else
        v_risk_type := 'risk_alert';
        v_label := null;
        v_evidence_type := case when v_source.source_type = 'media' then 'media_report' else 'risk_warning' end;
        v_evidence_level := 'C';
    end if;

    v_seen_at := coalesce(v_version.published_at, v_version.fetched_at);
    if p_draft->>'last_material_change_at' is not null
       and (p_draft->>'last_material_change_at')::timestamptz <> v_seen_at then
        raise exception using errcode = '23514', message = 'candidate_material_date_unverified';
    end if;
    v_family_id := substring(v_version.origin_group_key from 1 for 32)::uuid;
    insert into public.scam_patterns(slug,lifecycle_status,first_seen_at,last_seen_at)
    values('source-' || v_source.source_key || '-' || substring(v_version.content_hash from 1 for 12),
        'evidence_pending',v_seen_at,v_seen_at)
    returning id into v_pattern_id;
    v_content_hash := encode(extensions.digest(convert_to(p_draft::text, 'UTF8'), 'sha256'), 'hex');
    insert into public.pattern_revisions(
        pattern_id,revision_no,schema_version,canonical_name,short_name,pattern_type,risk_type,
        evidence_level,legal_status,public_evidence_label,one_sentence_summary,
        target_population,contact_channels,impersonated_identities,hooks,
        pressure_tactics,requested_actions,money_paths,technology_used,
        warning_signs,what_to_do,regions,first_seen_at,last_seen_at,last_material_change_at,
        evidence_set_hash,content_hash
    ) values (
        v_pattern_id,1,'pattern-revision-v1',v_canonical_name,v_short_name,p_draft->>'pattern_type',
        v_risk_type,v_evidence_level,v_legal_status,v_label,v_summary,
        array(select jsonb_array_elements_text(coalesce(p_draft->'target_population','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'contact_channels','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'impersonated_identities','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'hooks','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'pressure_tactics','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'requested_actions','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'money_paths','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'technology_used','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'warning_signs','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'what_to_do','[]'::jsonb))),
        array(select jsonb_array_elements_text(coalesce(p_draft->'regions','[]'::jsonb))),
        v_seen_at,v_seen_at,
        case when p_draft->>'last_material_change_at' is not null then v_seen_at else null end,
        repeat('0',64),v_content_hash
    ) returning id into v_revision_id;
    update public.scam_patterns set current_draft_revision_id = v_revision_id
    where id = v_pattern_id;
    insert into public.pattern_evidence(
        pattern_id,source_item_version_id,evidence_type,origin_group_key,
        evidence_family_id,claim_summary,event_date,is_material_update,
        last_verified_at,recheck_due_at
    ) values (
        v_pattern_id,p_version_id,v_evidence_type,v_version.origin_group_key,
        v_family_id,v_summary,v_seen_at::date,true,now(),now() + interval '30 days'
    ) returning id into v_evidence_id;
    v_evidence_hash := encode(extensions.digest(convert_to(
        v_evidence_id::text || ':' || v_version.content_hash || ':' ||
        v_version.origin_group_key || ':' || v_family_id::text || ':' || v_evidence_type,
        'UTF8'), 'sha256'), 'hex');
    update public.pattern_revisions set evidence_set_hash = v_evidence_hash
    where id = v_revision_id;

    for v_span in select value from jsonb_array_elements(p_spans) loop
        v_start := (v_span->>'start')::integer;
        v_end := (v_span->>'end')::integer;
        v_excerpt := v_span->>'excerpt';
        v_field := v_span->>'field_path';
        v_value := v_span->>'claim_value';
        if v_start < 0 or v_end <= v_start or v_end > char_length(v_version.clean_text)
           or v_end - v_start > 600
           or substring(v_version.clean_text from v_start + 1 for v_end - v_start) <> v_excerpt
           or v_field !~ '^[a-z][a-z0-9_]*(?:\[[1-9][0-9]*\])?$'
           or v_value is null or position(v_value in v_excerpt) = 0
        then
            raise exception using errcode = '23514', message = 'candidate_span_mismatch';
        end if;
        select field_path,value_hash into v_claim
        from private.revision_public_claims(v_revision_id)
        where field_path = v_field
          and value_hash = encode(extensions.digest(convert_to(v_value,'UTF8'),'sha256'),'hex');
        if not found then
            raise exception using errcode = '23514', message = 'candidate_claim_mismatch';
        end if;
        insert into public.evidence_spans(
            pattern_evidence_id,start_offset,end_offset,excerpt,excerpt_hash
        ) values (
            v_evidence_id,v_start,v_end,v_excerpt,
            encode(extensions.digest(convert_to(v_excerpt,'UTF8'),'sha256'),'hex')
        ) on conflict(pattern_evidence_id,start_offset,end_offset) do nothing
        returning id into v_span_id;
        if v_span_id is null then
            select id into v_span_id from public.evidence_spans
            where pattern_evidence_id = v_evidence_id
              and start_offset = v_start and end_offset = v_end
              and excerpt = v_excerpt;
            if v_span_id is null then
                raise exception using errcode = '23514', message = 'candidate_span_conflict';
            end if;
        end if;
        insert into public.evidence_claim_support(
            pattern_revision_id,field_path,value_hash,pattern_evidence_id,evidence_span_id
        ) values(v_revision_id,v_field,v_claim.value_hash,v_evidence_id,v_span_id)
        on conflict do nothing;
    end loop;
    select count(*) into v_missing_count
    from private.revision_public_claims(v_revision_id) as claim
    where not exists (
        select 1 from public.evidence_claim_support as support
        where support.pattern_revision_id = v_revision_id
          and support.field_path = claim.field_path
          and support.value_hash = claim.value_hash
    );
    v_status := case when v_missing_count = 0 and v_evidence_level = 'A'
        and p_draft->>'last_material_change_at' is not null
        and jsonb_array_length(coalesce(p_draft->'requested_actions','[]'::jsonb)) > 0
        then 'review_ready' else 'evidence_pending' end;
    update public.scam_patterns set lifecycle_status = v_status where id = v_pattern_id;

    v_heat_score := (p_heat->>'score')::integer;
    if v_heat_score not between 0 and 100
       or p_heat->>'version' <> 'scam-heat-v0.1'
       or p_heat->>'inputs_hash' !~ '^[0-9a-f]{64}$'
       or (p_heat->>'as_of')::date > current_date
       or jsonb_typeof(p_heat->'components') <> 'object'
       or (select count(*) from jsonb_object_keys(p_heat->'components')) <> 5
       or not (p_heat->'components' ?& array[
           'target_relevance','freshness','harm','spread','novelty'])
       or (select sum(value::integer) from jsonb_each_text(p_heat->'components')) <> v_heat_score
    then
        raise exception using errcode = '23514', message = 'candidate_heat_invalid';
    end if;
    v_heat_breakdown := jsonb_build_object(
        'target_relevance',jsonb_build_object('points',(p_heat #>> '{components,target_relevance}')::integer,
            'value',p_heat #>> '{feature_values,target_relevance}'),
        'freshness',jsonb_build_object('points',(p_heat #>> '{components,freshness}')::integer,
            'value',p_heat #>> '{feature_values,last_material_change_at}'),
        'harm',jsonb_build_object('points',(p_heat #>> '{components,harm}')::integer,
            'value',p_heat #>> '{feature_values,harm}'),
        'spread',jsonb_build_object('points',(p_heat #>> '{components,spread}')::integer,
            'value',p_heat #>> '{feature_values,spread}'),
        'novelty',jsonb_build_object('points',(p_heat #>> '{components,novelty}')::integer,
            'value',p_heat #>> '{feature_values,novelty}'),
        'total',v_heat_score
    );
    insert into public.heat_snapshots(pattern_id,score_version,as_of,score,breakdown,input_hash)
    values(v_pattern_id,'scam-heat-v0.1',(p_heat->>'as_of')::date,v_heat_score,
        v_heat_breakdown,p_heat->>'inputs_hash');
    insert into public.review_items(
        review_type,target_id,priority,heat_at_creation,evidence_level_at_creation,
        reason_codes,candidate_schema_version,candidate_payload,candidate_hash,
        base_row_version,dedupe_key
    ) values (
        'new_pattern',v_pattern_id,least(100,greatest(0,v_heat_score)),v_heat_score,
        v_evidence_level,coalesce(p_reason_codes,'{}'::text[]),
        'review-candidate-v1',p_candidate_payload,v_candidate_hash,1,
        'source-version:' || p_version_id::text
    ) returning id into v_review_id;
    insert into public.source_version_candidates(
        source_item_version_id,candidate_hash,pattern_id,revision_id,evidence_id,review_item_id
    ) values(p_version_id,v_candidate_hash,v_pattern_id,v_revision_id,v_evidence_id,v_review_id);
    return jsonb_build_object('pattern_id',v_pattern_id,'revision_id',v_revision_id,
        'evidence_id',v_evidence_id,'review_item_id',v_review_id,
        'missing_claim_count',v_missing_count,'lifecycle_status',v_status,
        'candidate_hash',v_candidate_hash,'replayed',false);
end;
$$;

revoke all on function public.submit_new_pattern_candidate(uuid,text,uuid,jsonb,jsonb,jsonb,jsonb,text[])
    from public, anon, authenticated;
grant execute on function public.submit_new_pattern_candidate(uuid,text,uuid,jsonb,jsonb,jsonb,jsonb,text[])
    to service_role;
commit;
