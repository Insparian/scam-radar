begin;

-- A newly collected item can propose evidence for an approved pattern, but
-- cannot change previously approved public wording or publish by itself.
create table public.source_version_updates (
    source_item_version_id uuid primary key references public.source_item_versions(id) on delete restrict,
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    pattern_id uuid not null references public.scam_patterns(id) on delete restrict,
    revision_id uuid not null unique references public.pattern_revisions(id) on delete restrict,
    evidence_id uuid not null unique references public.pattern_evidence(id) on delete restrict,
    review_item_id uuid not null unique references public.review_items(id) on delete restrict,
    created_at timestamptz not null default now()
);

alter table public.source_version_updates enable row level security;
revoke all on public.source_version_updates from public, anon, authenticated;
grant select on public.source_version_updates to service_role;

create or replace function public.submit_existing_pattern_evidence(
    p_version_id uuid,
    p_holder_id text,
    p_run_id uuid,
    p_pattern_id uuid,
    p_base_revision_id uuid,
    p_claim_summary text,
    p_comparison jsonb,
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
    v_pattern public.scam_patterns%rowtype;
    v_base public.pattern_revisions%rowtype;
    v_existing public.source_version_updates%rowtype;
    v_candidate_hash text;
    v_evidence_id uuid;
    v_revision_id uuid;
    v_review_id uuid;
    v_evidence_type text;
    v_evidence_hash text;
    v_content_hash text;
    v_seen_at timestamptz;
    v_heat_score integer;
begin
    perform private.assert_trusted_service();
    if p_holder_id !~ '^[a-zA-Z0-9:_-]{1,120}$'
       or p_claim_summary is null or char_length(p_claim_summary) not between 4 and 600
       or jsonb_typeof(p_comparison) <> 'object'
       or p_comparison->>'same_pattern' <> 'true'
       or (p_comparison->>'confidence')::numeric not between 0 and 1
       or jsonb_typeof(p_heat) <> 'object'
       or jsonb_typeof(p_candidate_payload) <> 'object'
       or octet_length(p_candidate_payload::text) > 30000
       or coalesce(cardinality(p_reason_codes),0) not between 1 and 30
    then
        raise exception using errcode = '23514', message = 'existing_candidate_shape_invalid';
    end if;
    select * into v_version from public.source_item_versions
    where id = p_version_id for update;
    if not found or v_version.processing_status <> 'processing'
       or v_version.claim_holder is distinct from p_holder_id
       or v_version.claimed_until <= now()
       or position(p_claim_summary in v_version.clean_text) = 0 then
        raise exception using errcode = '42501', message = 'existing_candidate_claim_invalid';
    end if;
    select source.* into v_source
    from public.source_items as item
    join public.sources as source on source.id = item.source_id
    where item.id = v_version.source_item_id;
    if not v_source.enabled or not v_source.collection_allowed
       or v_source.reviewed_at is null
       or not exists(select 1 from public.pipeline_runs
                     where id = p_run_id and outcome = 'running') then
        raise exception using errcode = '42501', message = 'existing_candidate_source_or_run_invalid';
    end if;
    v_candidate_hash := encode(extensions.digest(convert_to(jsonb_build_object(
        'pattern_id',p_pattern_id,'base_revision_id',p_base_revision_id,
        'summary',p_claim_summary,'comparison',p_comparison,'heat',p_heat,
        'payload',p_candidate_payload,'reasons',p_reason_codes
    )::text,'UTF8'),'sha256'),'hex');
    select * into v_existing from public.source_version_updates
    where source_item_version_id = p_version_id;
    if found then
        if v_existing.candidate_hash <> v_candidate_hash then
            raise exception using errcode = '23514', message = 'existing_candidate_replay_mismatch';
        end if;
        return jsonb_build_object('pattern_id',v_existing.pattern_id,
            'revision_id',v_existing.revision_id,'evidence_id',v_existing.evidence_id,
            'review_item_id',v_existing.review_item_id,
            'candidate_hash',v_existing.candidate_hash,'replayed',true);
    end if;
    select * into v_pattern from public.scam_patterns
    where id = p_pattern_id for update;
    select * into v_base from public.pattern_revisions
    where id = p_base_revision_id and pattern_id = p_pattern_id;
    if v_pattern.id is null or v_base.id is null
       or v_pattern.latest_approved_revision_id is distinct from v_base.id
       or v_pattern.current_draft_revision_id is not null
       or v_pattern.lifecycle_status <> 'review_ready'
       or v_base.revision_status <> 'approved' then
        raise exception using errcode = '23514', message = 'existing_candidate_base_changed';
    end if;
    if exists(select 1 from public.pattern_evidence
              where pattern_id = p_pattern_id and source_item_version_id = p_version_id) then
        raise exception using errcode = '23514', message = 'existing_candidate_duplicate_evidence';
    end if;
    v_seen_at := coalesce(v_version.published_at,v_version.fetched_at);
    v_evidence_type := case
        when v_source.source_type = 'court' then 'judgment'
        when v_source.source_type = 'police' then 'official_notice'
        when v_source.source_type = 'media' then 'media_report'
        else 'risk_warning' end;
    insert into public.pattern_evidence(
        pattern_id,source_item_version_id,evidence_type,origin_group_key,
        evidence_family_id,claim_summary,event_date,is_material_update,
        last_verified_at,recheck_due_at
    ) values (
        p_pattern_id,p_version_id,v_evidence_type,v_version.origin_group_key,
        substring(v_version.origin_group_key from 1 for 32)::uuid,
        p_claim_summary,v_seen_at::date,
        (p_comparison->>'material_change')::boolean,
        now(),now() + interval '30 days'
    ) returning id into v_evidence_id;
    select encode(extensions.digest(convert_to(coalesce(string_agg(
        evidence.id::text || ':' || version.content_hash || ':' ||
        evidence.origin_group_key || ':' || evidence.evidence_family_id::text || ':' ||
        evidence.evidence_type, '|' order by evidence.id),''),'UTF8'),'sha256'),'hex')
    into v_evidence_hash
    from public.pattern_evidence as evidence
    join public.source_item_versions as version
      on version.id = evidence.source_item_version_id
    where evidence.pattern_id = p_pattern_id
      and (evidence.acceptance_status = 'accepted' or evidence.id = v_evidence_id);
    v_content_hash := encode(extensions.digest(convert_to(
        v_base.content_hash || ':' || greatest(v_base.last_seen_at,v_seen_at)::text || ':' ||
        coalesce(case when (p_comparison->>'material_change')::boolean
            then greatest(coalesce(v_base.last_material_change_at,v_seen_at),v_seen_at)
            else v_base.last_material_change_at end::text,''),
        'UTF8'),'sha256'),'hex');
    insert into public.pattern_revisions(
        pattern_id,revision_no,schema_version,canonical_name,short_name,
        pattern_type,risk_type,evidence_level,legal_status,public_evidence_label,
        one_sentence_summary,target_population,contact_channels,
        impersonated_identities,hooks,common_phrases,pressure_tactics,
        requested_actions,money_paths,technology_used,warning_signs,what_to_do,
        regions,first_seen_at,last_seen_at,last_material_change_at,
        evidence_set_hash,content_hash
    ) values (
        p_pattern_id,(select max(revision_no) + 1 from public.pattern_revisions
                      where pattern_id = p_pattern_id),v_base.schema_version,
        v_base.canonical_name,v_base.short_name,v_base.pattern_type,
        v_base.risk_type,v_base.evidence_level,v_base.legal_status,
        v_base.public_evidence_label,v_base.one_sentence_summary,
        v_base.target_population,v_base.contact_channels,
        v_base.impersonated_identities,v_base.hooks,v_base.common_phrases,
        v_base.pressure_tactics,v_base.requested_actions,v_base.money_paths,
        v_base.technology_used,v_base.warning_signs,v_base.what_to_do,
        v_base.regions,v_base.first_seen_at,greatest(v_base.last_seen_at,v_seen_at),
        case when (p_comparison->>'material_change')::boolean
            then greatest(coalesce(v_base.last_material_change_at,v_seen_at),v_seen_at)
            else v_base.last_material_change_at end,
        v_evidence_hash,v_content_hash
    ) returning id into v_revision_id;
    insert into public.evidence_claim_support(
        pattern_revision_id,field_path,value_hash,pattern_evidence_id,evidence_span_id
    ) select v_revision_id,field_path,value_hash,pattern_evidence_id,evidence_span_id
      from public.evidence_claim_support where pattern_revision_id = v_base.id;
    update public.scam_patterns set current_draft_revision_id = v_revision_id
    where id = p_pattern_id;

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
    then raise exception using errcode = '23514', message = 'existing_candidate_heat_invalid'; end if;
    insert into public.heat_snapshots(pattern_id,score_version,as_of,score,breakdown,input_hash)
    values(p_pattern_id,'scam-heat-v0.1',(p_heat->>'as_of')::date,
        v_heat_score,jsonb_build_object(
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
            'total',v_heat_score),p_heat->>'inputs_hash');
    insert into public.review_items(
        review_type,target_id,priority,heat_at_creation,evidence_level_at_creation,
        reason_codes,candidate_schema_version,candidate_payload,candidate_hash,
        base_row_version,dedupe_key
    ) values (
        'pattern_update',p_pattern_id,least(100,greatest(0,v_heat_score)),
        v_heat_score,v_base.evidence_level,p_reason_codes,
        'review-candidate-v1',p_candidate_payload,v_candidate_hash,
        v_pattern.row_version,'source-version:' || p_version_id::text
    ) returning id into v_review_id;
    insert into public.source_version_updates(
        source_item_version_id,candidate_hash,pattern_id,revision_id,evidence_id,review_item_id
    ) values(p_version_id,v_candidate_hash,p_pattern_id,v_revision_id,v_evidence_id,v_review_id);
    return jsonb_build_object('pattern_id',p_pattern_id,'revision_id',v_revision_id,
        'evidence_id',v_evidence_id,'review_item_id',v_review_id,
        'candidate_hash',v_candidate_hash,'missing_claim_count',0,'replayed',false);
end;
$$;

revoke all on function public.submit_existing_pattern_evidence(
    uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[])
    from public, anon, authenticated;
grant execute on function public.submit_existing_pattern_evidence(
    uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[])
    to service_role;

commit;
