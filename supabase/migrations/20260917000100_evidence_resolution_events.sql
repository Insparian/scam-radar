begin;

create table public.evidence_resolution_events (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_evidence_id uuid not null unique
        references public.pattern_evidence (id) on delete restrict,
    outcome text not null check (outcome in ('accepted', 'rejected')),
    authority_path text not null check (
        authority_path in ('human', 'policy', 'legacy_unknown')
    ),
    actor_id uuid references public.admin_users (user_id) on delete restrict,
    policy_decision_id uuid references public.policy_decisions (id) on delete restrict,
    review_item_id uuid references public.review_items (id) on delete restrict,
    reason text not null check (btrim(reason) <> ''),
    reason_codes text[] not null check (cardinality(reason_codes) > 0),
    occurred_at timestamptz,
    created_at timestamptz not null default now(),
    constraint evidence_resolution_events_authority_shape check (
        (
            authority_path = 'human'
            and actor_id is not null
            and policy_decision_id is not null
            and review_item_id is not null
            and occurred_at is not null
        )
        or (
            authority_path = 'policy'
            and actor_id is null
            and policy_decision_id is not null
            and review_item_id is not null
            and occurred_at is not null
        )
        or (
            authority_path = 'legacy_unknown'
            and actor_id is null
            and policy_decision_id is null
            and review_item_id is null
            and occurred_at is null
        )
    ),
    constraint evidence_resolution_events_time_order check (
        occurred_at is null or occurred_at <= created_at
    )
);

comment on table public.evidence_resolution_events is
    'Append-only provenance for the one terminal accepted/rejected transition of each evidence row.';

create index evidence_resolution_events_review_item_idx
    on public.evidence_resolution_events (review_item_id, created_at);

create index evidence_resolution_events_policy_decision_idx
    on public.evidence_resolution_events (policy_decision_id, created_at);

insert into public.evidence_resolution_events (
    pattern_evidence_id,
    outcome,
    authority_path,
    actor_id,
    policy_decision_id,
    review_item_id,
    reason,
    reason_codes,
    occurred_at
)
select
    evidence.id,
    evidence.acceptance_status,
    'legacy_unknown',
    null,
    null,
    null,
    'pre_migration_resolution_provenance_unavailable',
    array['legacy_unknown'],
    null
from public.pattern_evidence as evidence
where evidence.acceptance_status in ('accepted', 'rejected');

create or replace function private.validate_evidence_resolution_event()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
    evidence_pattern_id uuid;
    decision public.policy_decisions%rowtype;
    queue_item public.review_items%rowtype;
begin
    select pattern_id into evidence_pattern_id
    from public.pattern_evidence
    where id = new.pattern_evidence_id
      and acceptance_status = new.outcome;

    if evidence_pattern_id is null then
        raise exception using errcode = '23514', message = 'evidence_resolution_state_mismatch';
    end if;

    if new.authority_path = 'legacy_unknown' then
        raise exception using errcode = '42501', message = 'legacy_resolution_events_are_migration_only';
    end if;

    select * into decision
    from public.policy_decisions
    where id = new.policy_decision_id;

    select * into queue_item
    from public.review_items
    where id = new.review_item_id;

    if decision.id is null
       or queue_item.id is null
       or decision.review_item_id is distinct from queue_item.id
       or decision.pattern_id is distinct from evidence_pattern_id
       or queue_item.target_id is distinct from evidence_pattern_id then
        raise exception using errcode = '23514', message = 'evidence_resolution_context_mismatch';
    end if;

    if new.authority_path = 'human' then
        perform private.assert_enabled_admin(new.actor_id);
        if new.actor_id is distinct from auth.uid() then
            raise exception using errcode = '42501', message = 'evidence_resolution_actor_mismatch';
        end if;
    elsif new.authority_path = 'policy' then
        perform private.assert_live_policy_execution(
            new.policy_decision_id,
            evidence_pattern_id,
            decision.pattern_revision_id
        );
    end if;

    return new;
end;
$$;

create trigger evidence_resolution_events_validate_insert
before insert on public.evidence_resolution_events
for each row execute function private.validate_evidence_resolution_event();

create trigger evidence_resolution_events_append_only
before update or delete on public.evidence_resolution_events
for each row execute function private.prevent_row_change();

create or replace function private.apply_evidence_decisions(
    p_pattern_id uuid,
    p_actor_id uuid,
    p_accepted_evidence_ids uuid[],
    p_rejected_evidence_ids uuid[]
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    accepted_ids uuid[] := coalesce(p_accepted_evidence_ids, '{}'::uuid[]);
    rejected_ids uuid[] := coalesce(p_rejected_evidence_ids, '{}'::uuid[]);
    exception_policy_decision_id uuid := private.current_human_exception_policy_id();
    resolution_reason text := nullif(
        current_setting('scam_radar.evidence_resolution_reason', true),
        ''
    );
    resolution_review_item_id uuid := nullif(
        current_setting('scam_radar.evidence_resolution_review_item_id', true),
        ''
    )::uuid;
    resolution_reason_codes text[];
    resolution_time timestamptz := now();
begin
    if cardinality(accepted_ids) <> (
        select count(distinct evidence_id) from unnest(accepted_ids) as evidence_id
    ) or cardinality(rejected_ids) <> (
        select count(distinct evidence_id) from unnest(rejected_ids) as evidence_id
    ) then
        raise exception using errcode = '22023', message = 'duplicate_evidence_decision';
    end if;

    if accepted_ids && rejected_ids then
        raise exception using errcode = '22023', message = 'conflicting_evidence_decision';
    end if;

    if resolution_reason is null or resolution_review_item_id is null then
        raise exception using errcode = '23514', message = 'evidence_resolution_context_required';
    end if;

    select reason_codes into resolution_reason_codes
    from public.policy_decisions
    where id = exception_policy_decision_id
      and review_item_id = resolution_review_item_id
      and pattern_id = p_pattern_id;

    if resolution_reason_codes is null then
        raise exception using errcode = '23514', message = 'evidence_resolution_policy_context_invalid';
    end if;

    if exists (
        select 1
        from unnest(accepted_ids || rejected_ids) as submitted_id
        where not exists (
            select 1
            from public.pattern_evidence as evidence
            where evidence.id = submitted_id
              and evidence.pattern_id = p_pattern_id
              and evidence.acceptance_status = 'proposed'
        )
    ) then
        raise exception using errcode = '22023', message = 'invalid_evidence_decision';
    end if;

    if exists (
        select 1
        from public.pattern_evidence as evidence
        where evidence.pattern_id = p_pattern_id
          and evidence.acceptance_status = 'proposed'
          and evidence.id <> all (accepted_ids || rejected_ids)
    ) then
        raise exception using errcode = '23514', message = 'all_proposed_evidence_requires_decision';
    end if;

    update public.pattern_evidence
    set acceptance_status = 'accepted',
        accepted_by = p_actor_id,
        accepted_at = resolution_time,
        acceptance_path = 'human',
        acceptance_policy_decision_id = exception_policy_decision_id
    where pattern_id = p_pattern_id
      and id = any (accepted_ids)
      and acceptance_status = 'proposed';

    update public.pattern_evidence
    set acceptance_status = 'rejected',
        accepted_by = null,
        accepted_at = null,
        acceptance_path = null,
        acceptance_policy_decision_id = null
    where pattern_id = p_pattern_id
      and id = any (rejected_ids)
      and acceptance_status = 'proposed';

    insert into public.evidence_resolution_events (
        pattern_evidence_id,
        outcome,
        authority_path,
        actor_id,
        policy_decision_id,
        review_item_id,
        reason,
        reason_codes,
        occurred_at,
        created_at
    )
    select
        evidence_id,
        outcome,
        'human',
        p_actor_id,
        exception_policy_decision_id,
        resolution_review_item_id,
        resolution_reason,
        resolution_reason_codes,
        resolution_time,
        resolution_time
    from (
        select unnest(accepted_ids) as evidence_id, 'accepted'::text as outcome
        union all
        select unnest(rejected_ids) as evidence_id, 'rejected'::text as outcome
    ) as resolved;
end;
$$;

create or replace function private.apply_policy_evidence_decisions(
    p_policy_decision_id uuid,
    p_pattern_id uuid,
    p_pattern_revision_id uuid,
    p_accepted_evidence_ids uuid[],
    p_rejected_evidence_ids uuid[]
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    accepted_ids uuid[] := coalesce(p_accepted_evidence_ids, '{}'::uuid[]);
    rejected_ids uuid[] := coalesce(p_rejected_evidence_ids, '{}'::uuid[]);
    resolution_review_item_id uuid;
    resolution_reason_codes text[];
    resolution_time timestamptz := now();
begin
    perform private.assert_live_policy_execution(
        p_policy_decision_id,
        p_pattern_id,
        p_pattern_revision_id
    );

    select review_item_id, reason_codes
    into resolution_review_item_id, resolution_reason_codes
    from public.policy_decisions
    where id = p_policy_decision_id;

    if cardinality(accepted_ids) <> (
        select count(distinct evidence_id) from unnest(accepted_ids) as evidence_id
    ) or cardinality(rejected_ids) <> (
        select count(distinct evidence_id) from unnest(rejected_ids) as evidence_id
    ) then
        raise exception using errcode = '22023', message = 'duplicate_evidence_decision';
    end if;

    if accepted_ids && rejected_ids then
        raise exception using errcode = '22023', message = 'conflicting_evidence_decision';
    end if;

    if resolution_review_item_id is null or resolution_reason_codes is null then
        raise exception using errcode = '23514', message = 'evidence_resolution_policy_context_invalid';
    end if;

    if exists (
        select 1
        from unnest(accepted_ids || rejected_ids) as submitted_id
        where not exists (
            select 1
            from public.pattern_evidence as evidence
            where evidence.id = submitted_id
              and evidence.pattern_id = p_pattern_id
              and evidence.acceptance_status = 'proposed'
        )
    ) then
        raise exception using errcode = '22023', message = 'invalid_evidence_decision';
    end if;

    if exists (
        select 1
        from public.pattern_evidence as evidence
        where evidence.pattern_id = p_pattern_id
          and evidence.acceptance_status = 'proposed'
          and evidence.id <> all (accepted_ids || rejected_ids)
    ) then
        raise exception using errcode = '23514', message = 'all_proposed_evidence_requires_decision';
    end if;

    update public.pattern_evidence
    set acceptance_status = 'accepted',
        accepted_by = null,
        accepted_at = resolution_time,
        acceptance_path = 'policy',
        acceptance_policy_decision_id = p_policy_decision_id
    where pattern_id = p_pattern_id
      and id = any (accepted_ids)
      and acceptance_status = 'proposed';

    update public.pattern_evidence
    set acceptance_status = 'rejected',
        accepted_by = null,
        accepted_at = null,
        acceptance_path = null,
        acceptance_policy_decision_id = null
    where pattern_id = p_pattern_id
      and id = any (rejected_ids)
      and acceptance_status = 'proposed';

    insert into public.evidence_resolution_events (
        pattern_evidence_id,
        outcome,
        authority_path,
        actor_id,
        policy_decision_id,
        review_item_id,
        reason,
        reason_codes,
        occurred_at,
        created_at
    )
    select
        evidence_id,
        outcome,
        'policy',
        null,
        p_policy_decision_id,
        resolution_review_item_id,
        'policy_decision:' || p_policy_decision_id::text,
        resolution_reason_codes,
        resolution_time,
        resolution_time
    from (
        select unnest(accepted_ids) as evidence_id, 'accepted'::text as outcome
        union all
        select unnest(rejected_ids) as evidence_id, 'rejected'::text as outcome
    ) as resolved;
end;
$$;

create or replace function public.confirm_policy_publication(
    p_policy_decision_id uuid,
    p_review_item_id uuid,
    p_draft_revision_id uuid,
    p_expected_row_version bigint,
    p_expected_candidate_hash text,
    p_expected_content_hash text,
    p_accepted_evidence_ids uuid[],
    p_rejected_evidence_ids uuid[],
    p_decision_note text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    queue_review_type text;
    approved_revision_id uuid;
begin
    perform private.assert_enabled_admin(auth.uid());

    select review_type into queue_review_type
    from public.review_items
    where id = p_review_item_id;

    if queue_review_type not in ('new_pattern', 'pattern_update') then
        raise exception using errcode = '23514', message = 'policy_exception_review_type_invalid';
    end if;

    perform private.assert_human_policy_exception(
        p_policy_decision_id,
        p_review_item_id,
        p_draft_revision_id
    );

    perform set_config(
        'scam_radar.human_exception_policy_decision_id',
        p_policy_decision_id::text,
        true
    );
    perform set_config(
        'scam_radar.evidence_resolution_reason',
        p_decision_note,
        true
    );
    perform set_config(
        'scam_radar.evidence_resolution_review_item_id',
        p_review_item_id::text,
        true
    );

    approved_revision_id := private.approve_review_item(
        queue_review_type,
        p_review_item_id,
        p_draft_revision_id,
        p_expected_row_version,
        p_expected_candidate_hash,
        p_expected_content_hash,
        p_accepted_evidence_ids,
        p_rejected_evidence_ids,
        p_decision_note
    );

    perform set_config('scam_radar.evidence_resolution_reason', '', true);
    perform set_config('scam_radar.evidence_resolution_review_item_id', '', true);

    return approved_revision_id;
end;
$$;

alter table public.evidence_resolution_events enable row level security;

revoke all on table public.evidence_resolution_events
    from public, anon, authenticated, service_role;

commit;
