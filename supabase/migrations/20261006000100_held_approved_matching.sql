begin;

-- Holding proposed evidence does not invalidate the previous approved facts.
-- Match only that approved revision; the pending draft still forces deferral.
-- Archived, rejected and never-approved patterns remain excluded.
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
        where pattern.lifecycle_status in ('review_ready', 'evidence_pending')
          and revision.revision_status = 'approved'
        order by (revision.pattern_type = p_pattern_type) desc,
            pattern.updated_at desc, pattern.id
        limit p_limit
    ) as candidate;
    return result;
end;
$$;

commit;
