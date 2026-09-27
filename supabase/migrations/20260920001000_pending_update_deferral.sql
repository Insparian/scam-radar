begin;

-- A matching item must see that an approved pattern is already awaiting review.
-- Hiding the pattern would incorrectly create a duplicate new pattern.
create or replace function public.list_pattern_match_candidates(
    p_pattern_type text,
    p_limit integer default 10
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare result jsonb;
begin
    perform private.assert_trusted_service();
    if p_pattern_type is null or char_length(p_pattern_type) not between 1 and 120
       or p_limit not between 1 and 10 then
        raise exception using errcode = '23514', message = 'match_candidate_request_invalid';
    end if;
    select coalesce(jsonb_agg(jsonb_build_object(
        'pattern_id', candidate.pattern_id,
        'revision_id', candidate.revision_id,
        'pattern_type', candidate.pattern_type,
        'canonical_name', candidate.canonical_name,
        'summary', candidate.one_sentence_summary,
        'impersonated_identities', candidate.impersonated_identities,
        'hooks', candidate.hooks,
        'pressure_tactics', candidate.pressure_tactics,
        'requested_actions', candidate.requested_actions,
        'money_paths', candidate.money_paths,
        'pending_review', candidate.pending_review
    ) order by candidate.rank, candidate.pattern_id), '[]'::jsonb)
    into result
    from (
        select pattern.id as pattern_id, revision.id as revision_id,
            revision.pattern_type, revision.canonical_name,
            revision.one_sentence_summary, revision.impersonated_identities,
            revision.hooks, revision.pressure_tactics,
            revision.requested_actions, revision.money_paths,
            pattern.current_draft_revision_id is not null as pending_review,
            row_number() over (order by
                (revision.pattern_type = p_pattern_type) desc,
                pattern.updated_at desc, pattern.id) as rank
        from public.scam_patterns as pattern
        join public.pattern_revisions as revision
          on revision.id = pattern.latest_approved_revision_id
        where pattern.lifecycle_status = 'review_ready'
          and revision.revision_status = 'approved'
        order by (revision.pattern_type = p_pattern_type) desc,
            pattern.updated_at desc, pattern.id
        limit p_limit
    ) as candidate;
    return result;
end;
$$;

-- A review conflict is not a model/source failure and cannot consume the
-- three-attempt claim budget. The next batch can retry after human resolution.
create function public.defer_source_version_for_review(
    p_version_id uuid,
    p_holder_id text,
    p_pattern_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_version public.source_item_versions%rowtype;
begin
    perform private.assert_trusted_service();
    select * into v_version from public.source_item_versions
    where id = p_version_id for update;
    if not found or v_version.processing_status <> 'processing'
       or v_version.claim_holder is distinct from p_holder_id
       or v_version.claimed_until <= now()
       or not exists (
           select 1 from public.scam_patterns
           where id = p_pattern_id
             and latest_approved_revision_id is not null
             and current_draft_revision_id is not null
       ) then
        raise exception using errcode = '42501', message = 'review_deferral_invalid';
    end if;
    update public.source_item_versions
    set processing_status = 'pending_ai',
        claim_holder = null,
        claimed_until = null,
        attempt_count = greatest(0, attempt_count - 1),
        last_error = 'pending_review_conflict'
    where id = p_version_id;
end;
$$;

revoke all on function public.defer_source_version_for_review(uuid,text,uuid)
    from public, anon, authenticated;
grant execute on function public.defer_source_version_for_review(uuid,text,uuid)
    to service_role;

commit;
