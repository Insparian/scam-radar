begin;

create or replace function public.get_existing_update_recovery(
    p_version_id uuid,
    p_holder_id text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_version public.source_item_versions%rowtype;
    v_update public.source_version_updates%rowtype;
    v_review public.review_items%rowtype;
    v_revision public.pattern_revisions%rowtype;
    v_evidence public.pattern_evidence%rowtype;
    v_pattern public.scam_patterns%rowtype;
    v_policy public.policy_decisions%rowtype;
    v_policy_count integer;
    v_candidate_hash text;
begin
    perform private.assert_trusted_service();
    if p_holder_id !~ '^[a-zA-Z0-9:_-]{1,120}$' then
        raise exception using errcode = '23514', message = 'invalid_recovery_holder';
    end if;
    select * into v_version from public.source_item_versions
    where id = p_version_id for update;
    if not found or v_version.processing_status <> 'processing'
       or v_version.claim_holder is distinct from p_holder_id
       or v_version.claimed_until <= now() then
        raise exception using errcode = '42501', message = 'existing_recovery_claim_invalid';
    end if;
    select * into v_update from public.source_version_updates
    where source_item_version_id = p_version_id;
    if not found then return null; end if;
    select * into v_review from public.review_items where id = v_update.review_item_id;
    select * into v_revision from public.pattern_revisions where id = v_update.revision_id;
    select * into v_evidence from public.pattern_evidence where id = v_update.evidence_id;
    select * into v_pattern from public.scam_patterns where id = v_update.pattern_id;
    if v_review.id is null or v_revision.id is null or v_evidence.id is null
       or v_pattern.id is null or v_review.review_type <> 'pattern_update'
       or v_review.target_id is distinct from v_update.pattern_id
       or v_review.dedupe_key <> 'source-version:' || p_version_id::text
       or v_review.candidate_hash <> v_update.candidate_hash
       or v_revision.pattern_id <> v_update.pattern_id
       or v_evidence.pattern_id <> v_update.pattern_id
       or v_evidence.source_item_version_id <> p_version_id
       or jsonb_typeof(v_review.candidate_payload) <> 'object'
       or v_review.candidate_payload->>'matched_pattern_id' <> v_update.pattern_id::text
       or v_review.candidate_payload->>'matched_revision_id' is null
    then
        raise exception using errcode = '23514', message = 'existing_recovery_receipt_invalid';
    end if;
    v_candidate_hash := encode(extensions.digest(convert_to(jsonb_build_object(
        'pattern_id',v_update.pattern_id,
        'base_revision_id',(v_review.candidate_payload->>'matched_revision_id')::uuid,
        'summary',v_evidence.claim_summary,
        'comparison',v_review.candidate_payload->'comparison',
        'heat',v_review.candidate_payload->'heat',
        'payload',v_review.candidate_payload,
        'reasons',v_review.reason_codes
    )::text,'UTF8'),'sha256'),'hex');
    if v_candidate_hash <> v_update.candidate_hash then
        raise exception using errcode = '23514', message = 'existing_recovery_hash_mismatch';
    end if;
    select count(*) into v_policy_count from public.policy_decisions
    where review_item_id = v_update.review_item_id;
    if v_policy_count > 1 then
        raise exception using errcode = '23514', message = 'existing_recovery_policy_ambiguous';
    end if;
    if v_policy_count = 1 then
        select * into v_policy from public.policy_decisions
        where review_item_id = v_update.review_item_id;
        if v_policy.pattern_id <> v_update.pattern_id
           or v_policy.pattern_revision_id <> v_update.revision_id
           or v_policy.candidate_hash <> v_update.candidate_hash
           or v_policy.surface <> 'public_database'
           or v_policy.execution_mode <> 'shadow'
           or v_policy.publication_authorized then
            raise exception using errcode = '23514', message = 'existing_recovery_policy_invalid';
        end if;
    end if;
    -- Human rejection is a valid terminal decision even if the worker crashed
    -- before writing a shadow Policy. The rejected draft can no longer accept
    -- a Policy row, so verify the human event and terminal rows instead.
    if v_review.status = 'rejected' then
        if v_review.resolved_at is null or v_review.assigned_to is null
           or nullif(btrim(v_review.decision_note),'') is null
           or v_revision.revision_status <> 'rejected'
           or v_evidence.acceptance_status <> 'rejected'
           or v_pattern.current_draft_revision_id is not distinct from v_update.revision_id
           or v_pattern.latest_approved_revision_id is not distinct from v_update.revision_id
           or not exists (
               select 1 from public.review_events as event
               where event.target_type = 'review_item'
                 and event.target_id = v_review.id
                 and event.actor_id = v_review.assigned_to
                 and event.action = 'reject'
                 and event.after_state::jsonb->>'status' = 'rejected'
           ) then
            raise exception using errcode = '23514', message = 'existing_recovery_rejection_invalid';
        end if;
    elsif v_review.status = 'approved' then
        if v_policy_count <> 1
           or v_review.resolved_at is null
           or v_revision.revision_status <> 'approved'
           or v_evidence.acceptance_status <> 'accepted'
           or v_pattern.current_draft_revision_id is not distinct from v_update.revision_id
        then
            raise exception using errcode = '23514', message = 'existing_recovery_approval_invalid';
        end if;
    elsif v_review.status in ('pending','in_review','needs_evidence') then
        if v_review.resolved_at is not null
           or v_revision.revision_status <> 'draft'
           or v_evidence.acceptance_status <> 'proposed'
           or v_pattern.current_draft_revision_id is distinct from v_update.revision_id
           or (v_policy_count = 0 and v_review.status in ('pending','in_review')
               and v_pattern.row_version <> v_review.base_row_version)
        then
            raise exception using errcode = '23514', message = 'existing_recovery_draft_invalid';
        end if;
    else
        raise exception using errcode = '23514', message = 'existing_recovery_review_status_invalid';
    end if;
    return jsonb_build_object(
        'pattern_id',v_update.pattern_id,
        'revision_id',v_update.revision_id,
        'evidence_id',v_update.evidence_id,
        'review_item_id',v_update.review_item_id,
        'candidate_hash',v_update.candidate_hash,
        'missing_claim_count',0,
        'candidate_payload',v_review.candidate_payload,
        'review_status',v_review.status,
        'policy_decision_id',v_policy.id,
        'policy_recordable',(v_policy_count = 0 and v_review.status in ('pending','in_review','needs_evidence')
            and v_pattern.row_version = v_review.base_row_version)
    );
end;
$$;

-- A human hold leaves the draft open but may change its row version. Wait for
-- the reviewer instead of repeatedly trying an invalid Policy insert.
create or replace function public.defer_recovered_update_for_review(
    p_version_id uuid, p_holder_id text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare v_receipt jsonb;
begin
    perform private.assert_trusted_service();
    v_receipt := public.get_existing_update_recovery(p_version_id,p_holder_id);
    if v_receipt is null
       or v_receipt->>'review_status' <> 'needs_evidence'
       or v_receipt->>'policy_recordable' <> 'false'
       or v_receipt->>'policy_decision_id' is not null then
        raise exception using errcode = '42501', message = 'existing_hold_deferral_invalid';
    end if;
    update public.source_item_versions
    set processing_status = 'pending_ai',
        claim_holder = null,
        claimed_until = null,
        attempt_count = greatest(0,attempt_count - 1),
        last_error = 'awaiting_evidence_review'
    where id = p_version_id;
end;
$$;
revoke all on function public.defer_recovered_update_for_review(uuid,text)
    from public, anon, authenticated;
grant execute on function public.defer_recovered_update_for_review(uuid,text)
    to service_role;


-- Holding an existing approved pattern changes only reviewer workflow state.
-- Keep its row version so a delayed shadow Policy can still bind to the
-- unchanged draft, and the reviewer can later approve it with that Policy.
create or replace function public.hold_for_evidence(
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

    if not found or queue_item.status not in ('pending', 'in_review') then
        raise exception using errcode = '23514', message = 'review_item_not_holdable';
    end if;

    if queue_item.candidate_hash is distinct from p_expected_candidate_hash then
        raise exception using errcode = '40001', message = 'candidate_changed';
    end if;

    update public.review_items
    set status = 'needs_evidence',
        assigned_to = actor_id,
        decision_note = p_decision_note
    where id = queue_item.id;

    update public.scam_patterns
    set lifecycle_status = 'evidence_pending',
        row_version = row_version + case when queue_item.review_type = 'pattern_update' then 0 else 1 end
    where id = queue_item.target_id
      and lifecycle_status <> 'archived';

    event_id := private.append_review_event(
        actor_id,
        'hold_for_evidence',
        'review_item',
        queue_item.id,
        jsonb_build_object('status', queue_item.status)::text,
        jsonb_build_object('status', 'needs_evidence')::text,
        p_decision_note
    );

    return event_id;
end;
$$;

-- The rejected held draft has been removed by the reviewer transaction. Put
-- the still-approved public pattern back into the matchable review_ready state.
create function private.restore_existing_pattern_after_held_rejection()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if old.status = 'needs_evidence'
       and new.status = 'rejected'
       and new.review_type = 'pattern_update' then
        update public.scam_patterns
        set lifecycle_status = 'review_ready'
        where id = new.target_id
          and lifecycle_status = 'evidence_pending'
          and latest_approved_revision_id is not null
          and current_draft_revision_id is null;
        if not found then
            raise exception using errcode = '23514', message = 'held_rejection_pattern_state_invalid';
        end if;
    end if;
    return new;
end;
$$;
create trigger restore_existing_pattern_after_held_rejection
    after update of status on public.review_items
    for each row execute function private.restore_existing_pattern_after_held_rejection();

commit;
