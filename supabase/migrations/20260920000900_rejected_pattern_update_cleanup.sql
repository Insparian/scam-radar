begin;

-- Rejecting an update must release its draft slot without changing the last
-- approved revision. The proposed evidence is resolved with the rejected draft.
create or replace function public.reject_review_item(
    p_review_item_id uuid,
    p_expected_candidate_hash text,
    p_decision_note text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    actor_id uuid := auth.uid();
    queue_item public.review_items%rowtype;
    pattern public.scam_patterns%rowtype;
    update_item public.source_version_updates%rowtype;
    event_id uuid;
begin
    perform private.assert_enabled_admin(actor_id);

    if btrim(coalesce(p_decision_note, '')) = '' then
        raise exception using errcode = '23514', message = 'decision_note_required';
    end if;

    select * into queue_item
    from public.review_items
    where id = p_review_item_id
    for update;

    if not found or queue_item.status not in ('pending', 'in_review', 'needs_evidence') then
        raise exception using errcode = '23514', message = 'review_item_not_resolvable';
    end if;

    if queue_item.candidate_hash is distinct from p_expected_candidate_hash then
        raise exception using errcode = '40001', message = 'candidate_changed';
    end if;

    if queue_item.review_type = 'pattern_update' then
        select * into pattern from public.scam_patterns
        where id = queue_item.target_id for update;
        select * into update_item from public.source_version_updates
        where review_item_id = queue_item.id;
        if pattern.latest_approved_revision_id is null
           or pattern.current_draft_revision_id is distinct from update_item.revision_id
           or update_item.pattern_id is distinct from pattern.id then
            raise exception using errcode = '40001', message = 'update_draft_changed';
        end if;
        update public.pattern_evidence set acceptance_status = 'rejected'
        where id = update_item.evidence_id and acceptance_status = 'proposed';
        if not found then
            raise exception using errcode = '40001', message = 'update_evidence_changed';
        end if;
        update public.pattern_revisions set revision_status = 'rejected'
        where id = update_item.revision_id and revision_status = 'draft';
        if not found then
            raise exception using errcode = '40001', message = 'update_revision_changed';
        end if;
        update public.scam_patterns
        set current_draft_revision_id = null, row_version = row_version + 1
        where id = pattern.id;
    end if;

    update public.review_items
    set status = 'rejected',
        assigned_to = actor_id,
        decision_note = p_decision_note,
        resolved_at = now()
    where id = queue_item.id;

    update public.scam_patterns
    set lifecycle_status = 'rejected',
        row_version = row_version + 1
    where id = queue_item.target_id
      and latest_approved_revision_id is null;

    event_id := private.append_review_event(
        actor_id,
        'reject',
        'review_item',
        queue_item.id,
        jsonb_build_object('status', queue_item.status, 'candidate_hash', queue_item.candidate_hash)::text,
        jsonb_build_object('status', 'rejected')::text,
        p_decision_note
    );

    return event_id;
end;
$$;

commit;
