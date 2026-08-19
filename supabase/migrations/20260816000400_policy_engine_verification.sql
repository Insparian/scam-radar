begin;

create table public.policy_decisions (
    id uuid primary key default extensions.gen_random_uuid(),
    pattern_id uuid not null references public.scam_patterns (id) on delete restrict,
    pattern_revision_id uuid not null,
    review_item_id uuid not null references public.review_items (id) on delete restrict,
    pipeline_run_id uuid not null references public.pipeline_runs (id) on delete restrict,
    surface text not null check (surface in ('public_database', 'distribution')),
    policy_version text not null check (btrim(policy_version) <> ''),
    policy_hash text not null check (policy_hash ~ '^[0-9a-f]{64}$'),
    input_hash text not null check (input_hash ~ '^[0-9a-f]{64}$'),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    evidence_set_hash text not null check (evidence_set_hash ~ '^[0-9a-f]{64}$'),
    candidate_hash text not null check (candidate_hash ~ '^[0-9a-f]{64}$'),
    base_row_version bigint not null check (base_row_version > 0),
    gate_version text not null check (btrim(gate_version) <> ''),
    gate_outcome text not null check (
        gate_outcome in ('eligible_for_policy', 'needs_more_evidence', 'blocked', 'duplicate')
    ),
    rules_outcome text not null check (
        rules_outcome in ('safe_to_automate', 'review_required', 'blocked')
    ),
    decision_outcome text not null check (
        decision_outcome in ('safe_to_automate', 'review_required', 'blocked')
    ),
    execution_mode text not null check (execution_mode in ('shadow', 'live')),
    publication_authorized boolean not null,
    model_confidence numeric(6, 5) check (
        model_confidence is null or model_confidence between 0 and 1
    ),
    model_confidence_downgrade boolean not null default false,
    reason_codes text[] not null check (cardinality(reason_codes) > 0),
    evaluated_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    constraint policy_decisions_revision_pattern_fk foreign key (pattern_revision_id, pattern_id)
        references public.pattern_revisions (id, pattern_id) on delete restrict,
    constraint policy_decisions_never_increase_authority check (
        (rules_outcome = 'safe_to_automate')
        or (rules_outcome = 'review_required' and decision_outcome in ('review_required', 'blocked'))
        or (rules_outcome = 'blocked' and decision_outcome = 'blocked')
    ),
    constraint policy_decisions_confidence_only_downgrades check (
        (
            not model_confidence_downgrade
            and decision_outcome = rules_outcome
        )
        or (
            model_confidence_downgrade
            and rules_outcome = 'safe_to_automate'
            and decision_outcome = 'review_required'
        )
    ),
    constraint policy_decisions_gate_authority check (
        gate_outcome = 'eligible_for_policy'
        or (
            rules_outcome = 'blocked'
            and decision_outcome = 'blocked'
        )
    ),
    constraint policy_decisions_publication_authority check (
        not publication_authorized
        or (
            execution_mode = 'live'
            and decision_outcome = 'safe_to_automate'
        )
    ),
    constraint policy_decisions_time_order check (created_at >= evaluated_at),
    constraint policy_decisions_behavior_unique unique (
        pattern_revision_id,
        review_item_id,
        pipeline_run_id,
        surface,
        policy_version,
        policy_hash,
        input_hash,
        execution_mode
    )
);

alter table public.pattern_evidence
    add column acceptance_path text check (acceptance_path in ('human', 'policy')),
    add column acceptance_policy_decision_id uuid references public.policy_decisions (id) on delete restrict;

alter table public.pattern_revisions
    add column verified_at timestamptz,
    add column verification_path text check (verification_path in ('human', 'policy')),
    add column verification_policy_decision_id uuid references public.policy_decisions (id) on delete restrict,
    add column verification_review_event_id uuid references public.review_events (id) on delete restrict;

alter table public.publication_changes
    add column request_path text not null default 'human' check (request_path in ('human', 'policy')),
    add column policy_decision_id uuid references public.policy_decisions (id) on delete restrict,
    alter column requested_by drop not null;

alter table public.public_release_items
    add column last_verified_at timestamptz;

alter table public.public_releases
    add column published_at timestamptz,
    add column schema_version integer not null default 1 check (schema_version in (1, 2));

alter table public.pattern_evidence
    add constraint pattern_evidence_id_pattern_unique unique (id, pattern_id);

create table public.public_release_evidence_items (
    release_id uuid not null,
    pattern_id uuid not null,
    pattern_evidence_id uuid not null,
    last_verified_at timestamptz not null,
    created_at timestamptz not null default now(),
    primary key (release_id, pattern_id, pattern_evidence_id),
    constraint public_release_evidence_items_release_pattern_fk
        foreign key (release_id, pattern_id)
        references public.public_release_items (release_id, pattern_id) on delete restrict,
    constraint public_release_evidence_items_evidence_pattern_fk
        foreign key (pattern_evidence_id, pattern_id)
        references public.pattern_evidence (id, pattern_id) on delete restrict
);

alter table public.pattern_evidence disable trigger pattern_evidence_protect_resolution;
update public.pattern_evidence
set acceptance_path = 'human'
where acceptance_status = 'accepted';
alter table public.pattern_evidence enable trigger pattern_evidence_protect_resolution;

alter table public.pattern_revisions disable trigger pattern_revisions_protect_approval;
update public.pattern_revisions as revision
set verified_at = revision.approved_at,
    verification_path = 'human',
    verification_review_event_id = (
        select event.id
        from public.review_events as event
        where event.target_type = 'pattern_revision'
          and event.target_id = revision.id
          and event.actor_id = revision.approved_by
        order by event.created_at desc, event.id desc
        limit 1
    )
where revision.revision_status = 'approved';
alter table public.pattern_revisions enable trigger pattern_revisions_protect_approval;

update public.public_releases
set published_at = prepared_at
where published_at is null;

alter table public.public_releases
    alter column published_at set not null;

alter table public.pattern_evidence
    drop constraint pattern_evidence_acceptance_shape,
    add constraint pattern_evidence_acceptance_shape check (
        (
            acceptance_status = 'accepted'
            and accepted_at is not null
            and evidence_family_id is not null
            and (
                (
                    acceptance_path = 'human'
                    and accepted_by is not null
                )
                or (
                    acceptance_path = 'policy'
                    and accepted_by is null
                    and acceptance_policy_decision_id is not null
                )
            )
        )
        or (
            acceptance_status <> 'accepted'
            and accepted_by is null
            and accepted_at is null
            and acceptance_path is null
            and acceptance_policy_decision_id is null
        )
    );

alter table public.pattern_revisions
    drop constraint pattern_revisions_approval_shape,
    add constraint pattern_revisions_approval_shape check (
        (
            revision_status = 'approved'
            and verified_at is not null
            and (
                (
                    verification_path = 'human'
                    and approved_by is not null
                    and approved_at is not null
                    and verification_review_event_id is not null
                )
                or (
                    verification_path = 'policy'
                    and approved_by is null
                    and approved_at is null
                    and verification_policy_decision_id is not null
                    and verification_review_event_id is null
                )
            )
        )
        or (
            revision_status <> 'approved'
            and approved_by is null
            and approved_at is null
            and verified_at is null
            and verification_path is null
            and verification_policy_decision_id is null
            and verification_review_event_id is null
        )
    );

alter table public.publication_changes
    add constraint publication_changes_provenance_shape check (
        (
            request_path = 'human'
            and requested_by is not null
            and review_event_id is not null
        )
        or (
            request_path = 'policy'
            and requested_by is null
            and review_event_id is null
            and policy_decision_id is not null
        )
    );

create index policy_decisions_revision_idx
    on public.policy_decisions (pattern_revision_id, evaluated_at desc, id desc);
create index policy_decisions_review_item_idx
    on public.policy_decisions (review_item_id, evaluated_at desc, id desc);
create index policy_decisions_outcome_idx
    on public.policy_decisions (surface, execution_mode, decision_outcome, evaluated_at desc);
create index pattern_evidence_acceptance_policy_idx
    on public.pattern_evidence (acceptance_policy_decision_id)
    where acceptance_policy_decision_id is not null;
create index pattern_revisions_verification_policy_idx
    on public.pattern_revisions (verification_policy_decision_id)
    where verification_policy_decision_id is not null;
create index publication_changes_policy_idx
    on public.publication_changes (policy_decision_id)
    where policy_decision_id is not null;

alter table public.policy_decisions enable row level security;
alter table public.public_release_evidence_items enable row level security;
revoke all on table public.policy_decisions from public, anon, authenticated;
revoke all on table public.public_release_evidence_items from public, anon, authenticated;

create or replace function private.assert_enabled_admin(p_actor uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    jwt_role text := coalesce(
        nullif(current_setting('request.jwt.claim.role', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'
    );
begin
    if jwt_role is distinct from 'authenticated' then
        raise exception using errcode = '42501', message = 'authenticated_reviewer_role_required';
    end if;

    if auth.uid() is null then
        raise exception using errcode = '42501', message = 'reviewer_identity_required';
    end if;

    if p_actor is distinct from auth.uid() then
        raise exception using errcode = '42501', message = 'reviewer_identity_mismatch';
    end if;

    if not exists (
        select 1
        from public.admin_users as admin_user
        where admin_user.user_id = auth.uid()
          and admin_user.enabled
          and admin_user.role in ('reviewer', 'admin')
    ) then
        raise exception using errcode = '42501', message = 'enabled_reviewer_required';
    end if;
end;
$$;

create or replace function private.active_live_publication_policies()
returns table (policy_version text, policy_hash text, gate_version text)
language sql
immutable
security definer
set search_path = ''
as $$
    select
        null::text as policy_version,
        null::text as policy_hash,
        null::text as gate_version
    where false;
$$;

create or replace function private.current_human_exception_policy_id()
returns uuid
language sql
stable
security invoker
set search_path = ''
as $$
    select nullif(current_setting('scam_radar.human_exception_policy_decision_id', true), '')::uuid;
$$;

create or replace function private.current_policy_execution_id()
returns uuid
language sql
stable
security invoker
set search_path = ''
as $$
    select nullif(current_setting('scam_radar.policy_execution_decision_id', true), '')::uuid;
$$;

create or replace function private.revision_last_verified_at(p_revision_id uuid)
returns timestamptz
language sql
stable
security invoker
set search_path = ''
as $$
    with supporting_evidence as (
        select distinct support.pattern_evidence_id
        from private.revision_public_claims(p_revision_id) as claim
        join public.evidence_claim_support as support
          on support.pattern_revision_id = p_revision_id
         and support.field_path = claim.field_path
         and support.value_hash = claim.value_hash
        join public.pattern_evidence as evidence
          on evidence.id = support.pattern_evidence_id
        where evidence.acceptance_status = 'accepted'
    )
    select case
        when count(*) = 0 then null
        when count(evidence.last_verified_at) <> count(*) then null
        else min(evidence.last_verified_at)
    end
    from supporting_evidence
    join public.pattern_evidence as evidence
      on evidence.id = supporting_evidence.pattern_evidence_id;
$$;

create or replace function private.assert_public_claim_evidence_verified(p_revision_id uuid)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if exists (
        select 1
        from private.revision_public_claims(p_revision_id) as claim
        join public.evidence_claim_support as support
          on support.pattern_revision_id = p_revision_id
         and support.field_path = claim.field_path
         and support.value_hash = claim.value_hash
        join public.pattern_evidence as evidence
          on evidence.id = support.pattern_evidence_id
        where evidence.acceptance_status = 'accepted'
          and evidence.last_verified_at is null
    ) then
        raise exception using errcode = '23514', message = 'public_claim_evidence_verification_required';
    end if;
end;
$$;

create or replace function private.assert_human_policy_exception(
    p_policy_decision_id uuid,
    p_review_item_id uuid,
    p_pattern_revision_id uuid
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    decision public.policy_decisions%rowtype;
    revision public.pattern_revisions%rowtype;
    queue_item public.review_items%rowtype;
    pattern public.scam_patterns%rowtype;
begin
    select * into decision
    from public.policy_decisions
    where id = p_policy_decision_id;

    select * into revision
    from public.pattern_revisions
    where id = p_pattern_revision_id;

    select * into queue_item
    from public.review_items
    where id = p_review_item_id;

    select * into pattern
    from public.scam_patterns
    where id = revision.pattern_id;

    if decision.id is null
       or revision.id is null
       or queue_item.id is null
       or pattern.id is null
       or decision.surface <> 'public_database'
       or decision.decision_outcome = 'blocked'
       or not (
           (
               decision.execution_mode = 'shadow'
               and not decision.publication_authorized
           )
           or (
               decision.execution_mode = 'live'
               and decision.decision_outcome = 'review_required'
               and not decision.publication_authorized
               and exists (
                   select 1
                   from private.active_live_publication_policies() as active_policy
                   where active_policy.policy_version = decision.policy_version
                     and active_policy.policy_hash = decision.policy_hash
                     and active_policy.gate_version = decision.gate_version
               )
           )
       )
       or decision.review_item_id <> queue_item.id
       or decision.pattern_revision_id <> revision.id
       or decision.pattern_id <> revision.pattern_id
       or decision.content_hash <> revision.content_hash
       or decision.evidence_set_hash <> revision.evidence_set_hash
       or decision.candidate_hash <> queue_item.candidate_hash
       or decision.base_row_version <> queue_item.base_row_version
       or decision.base_row_version <> pattern.row_version then
        raise exception using errcode = '40001', message = 'policy_decision_not_valid_human_exception';
    end if;
end;
$$;

create or replace function private.assert_live_policy_execution(
    p_policy_decision_id uuid,
    p_pattern_id uuid,
    p_pattern_revision_id uuid
)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    decision public.policy_decisions%rowtype;
    revision public.pattern_revisions%rowtype;
    queue_item public.review_items%rowtype;
    pattern public.scam_patterns%rowtype;
begin
    if private.current_policy_execution_id() is distinct from p_policy_decision_id then
        raise exception using errcode = '42501', message = 'policy_execution_context_required';
    end if;

    select * into decision
    from public.policy_decisions
    where id = p_policy_decision_id;

    select * into revision
    from public.pattern_revisions
    where id = p_pattern_revision_id;

    select * into queue_item
    from public.review_items
    where id = decision.review_item_id;

    select * into pattern
    from public.scam_patterns
    where id = p_pattern_id;

    if decision.id is null
       or revision.id is null
       or queue_item.id is null
       or pattern.id is null
       or decision.execution_mode <> 'live'
       or decision.surface <> 'public_database'
       or decision.decision_outcome <> 'safe_to_automate'
       or not decision.publication_authorized
       or not exists (
           select 1
           from private.active_live_publication_policies() as active_policy
           where active_policy.policy_version = decision.policy_version
             and active_policy.policy_hash = decision.policy_hash
             and active_policy.gate_version = decision.gate_version
       )
       or decision.pattern_id <> pattern.id
       or decision.pattern_revision_id <> revision.id
       or revision.pattern_id <> pattern.id
       or decision.content_hash <> revision.content_hash
       or decision.evidence_set_hash <> revision.evidence_set_hash
       or decision.candidate_hash <> queue_item.candidate_hash
       or decision.base_row_version <> queue_item.base_row_version
       or pattern.row_version not in (
           decision.base_row_version,
           decision.base_row_version + 1
       ) then
        raise exception using errcode = '40001', message = 'live_policy_decision_stale_inactive_or_unsafe';
    end if;
end;
$$;

create or replace function private.validate_policy_decision_insert()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
    revision public.pattern_revisions%rowtype;
    queue_item public.review_items%rowtype;
    pattern public.scam_patterns%rowtype;
begin
    perform private.assert_trusted_service();

    select * into revision
    from public.pattern_revisions
    where id = new.pattern_revision_id;

    select * into queue_item
    from public.review_items
    where id = new.review_item_id;

    select * into pattern
    from public.scam_patterns
    where id = new.pattern_id;

    if revision.id is null
       or queue_item.id is null
       or pattern.id is null
       or revision.revision_status <> 'draft'
       or revision.pattern_id <> pattern.id
       or queue_item.target_id <> pattern.id
       or queue_item.status not in ('pending', 'in_review', 'needs_evidence')
       or new.content_hash <> revision.content_hash
       or new.evidence_set_hash <> revision.evidence_set_hash
       or new.candidate_hash <> queue_item.candidate_hash
       or new.base_row_version <> queue_item.base_row_version
       or new.base_row_version <> pattern.row_version then
        raise exception using errcode = '40001', message = 'policy_decision_input_stale';
    end if;

    if new.publication_authorized and not exists (
        select 1
        from private.active_live_publication_policies() as active_policy
        where active_policy.policy_version = new.policy_version
          and active_policy.policy_hash = new.policy_hash
          and active_policy.gate_version = new.gate_version
    ) then
        raise exception using errcode = '42501', message = 'policy_live_publication_policy_inactive';
    end if;

    return new;
end;
$$;

create trigger policy_decisions_validate_insert
before insert on public.policy_decisions
for each row execute function private.validate_policy_decision_insert();

create trigger policy_decisions_append_only
before update or delete on public.policy_decisions
for each row execute function private.prevent_row_change();

create or replace function private.protect_review_resolution()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
    policy_decision_id uuid;
    policy_revision_id uuid;
begin
    if tg_op = 'INSERT' then
        if new.status <> 'pending' then
            raise exception using errcode = '23514', message = 'review_item_must_start_pending';
        end if;
        return new;
    end if;

    if old.status is distinct from new.status
       and new.status in ('in_review', 'needs_evidence', 'approved', 'rejected', 'merged') then
        policy_decision_id := private.current_policy_execution_id();

        if new.status = 'approved'
           and new.assigned_to is null
           and policy_decision_id is not null then
            select pattern_revision_id into policy_revision_id
            from public.policy_decisions
            where id = policy_decision_id;

            perform private.assert_live_policy_execution(
                policy_decision_id,
                new.target_id,
                policy_revision_id
            );
        else
            perform private.assert_enabled_admin(new.assigned_to);
        end if;
    end if;

    return new;
end;
$$;

create or replace function private.protect_pattern_revision()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
    current_policy_decision public.policy_decisions%rowtype;
begin
    if tg_op = 'INSERT' then
        if new.revision_status = 'approved' then
            raise exception using errcode = '23514', message = 'approved_revision_must_transition_from_draft';
        end if;
        return new;
    end if;

    if tg_op = 'DELETE' then
        if old.revision_status = 'approved' then
            raise exception using errcode = '55000', message = 'approved_revision_is_immutable';
        end if;
        return old;
    end if;

    if old.revision_status = 'approved' then
        raise exception using errcode = '55000', message = 'approved_revision_is_immutable';
    end if;

    if new.revision_status = 'approved' and old.revision_status <> 'approved' then
        select decision.* into current_policy_decision
        from public.policy_decisions as decision
        join public.review_items as queue_item on queue_item.id = decision.review_item_id
        join public.scam_patterns as pattern on pattern.id = decision.pattern_id
        where decision.pattern_revision_id = new.id
          and decision.surface = 'public_database'
          and decision.content_hash = new.content_hash
          and decision.evidence_set_hash = new.evidence_set_hash
          and decision.candidate_hash = queue_item.candidate_hash
          and decision.base_row_version = queue_item.base_row_version
          and decision.base_row_version = pattern.row_version
        order by decision.evaluated_at desc, decision.id desc
        limit 1;

        if current_policy_decision.id is not null
           and current_policy_decision.decision_outcome = 'blocked' then
            raise exception using errcode = '42501', message = 'policy_decision_blocked_publication';
        end if;

        if current_policy_decision.id is not null
           and new.verification_policy_decision_id is distinct from current_policy_decision.id then
            raise exception using errcode = '23514', message = 'current_policy_provenance_required';
        end if;

        if new.verification_path = 'human' then
            perform private.assert_enabled_admin(new.approved_by);

            if new.verification_review_event_id is null or not exists (
                select 1
                from public.review_events
                where id = new.verification_review_event_id
                  and actor_id = new.approved_by
                  and target_type = 'pattern_revision'
                  and target_id = new.id
            ) then
                raise exception using errcode = '23514', message = 'human_verification_event_required';
            end if;

            if new.verification_policy_decision_id is not null then
                perform private.assert_human_policy_exception(
                    new.verification_policy_decision_id,
                    current_policy_decision.review_item_id,
                    new.id
                );
            end if;
        elsif new.verification_path = 'policy' then
            perform private.assert_live_policy_execution(
                new.verification_policy_decision_id,
                new.pattern_id,
                new.id
            );
        else
            raise exception using errcode = '23514', message = 'verification_path_required';
        end if;

        perform private.assert_publishable_revision(new.id);
        perform private.assert_public_claim_evidence_verified(new.id);
    end if;

    return new;
end;
$$;

create or replace function private.protect_resolved_evidence()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
    policy_decision_id uuid;
    policy_review_item_id uuid;
    policy_revision_id uuid;
begin
    if tg_op = 'INSERT' then
        if new.acceptance_status <> 'proposed'
           or new.acceptance_path is not null
           or new.acceptance_policy_decision_id is not null then
            raise exception using errcode = '23514', message = 'evidence_must_start_proposed';
        end if;
        return new;
    end if;

    if tg_op = 'DELETE' then
        raise exception using errcode = '55000', message = 'pattern_evidence_is_retained';
    end if;

    if old.acceptance_status = 'proposed' and new.acceptance_status = 'accepted' then
        if new.acceptance_path = 'human' then
            perform private.assert_enabled_admin(new.accepted_by);

            if new.acceptance_policy_decision_id is not null then
                select review_item_id, pattern_revision_id
                into policy_review_item_id, policy_revision_id
                from public.policy_decisions
                where id = new.acceptance_policy_decision_id;

                perform private.assert_human_policy_exception(
                    new.acceptance_policy_decision_id,
                    policy_review_item_id,
                    policy_revision_id
                );
            end if;
        elsif new.acceptance_path = 'policy' then
            select pattern_revision_id into policy_revision_id
            from public.policy_decisions
            where id = new.acceptance_policy_decision_id;

            perform private.assert_live_policy_execution(
                new.acceptance_policy_decision_id,
                new.pattern_id,
                policy_revision_id
            );
        else
            raise exception using errcode = '23514', message = 'evidence_acceptance_provenance_required';
        end if;
    elsif old.acceptance_status = 'proposed' and new.acceptance_status = 'rejected' then
        policy_decision_id := private.current_policy_execution_id();

        if policy_decision_id is null then
            perform private.assert_enabled_admin(auth.uid());
        else
            select pattern_revision_id into policy_revision_id
            from public.policy_decisions
            where id = policy_decision_id;

            perform private.assert_live_policy_execution(
                policy_decision_id,
                new.pattern_id,
                policy_revision_id
            );
        end if;
    end if;

    if old.acceptance_status in ('accepted', 'rejected') and (
        old.id is distinct from new.id
        or old.pattern_id is distinct from new.pattern_id
        or old.source_item_version_id is distinct from new.source_item_version_id
        or old.evidence_type is distinct from new.evidence_type
        or old.origin_group_key is distinct from new.origin_group_key
        or old.evidence_family_id is distinct from new.evidence_family_id
        or old.claim_summary is distinct from new.claim_summary
        or old.event_date is distinct from new.event_date
        or old.region is distinct from new.region
        or old.victim_count is distinct from new.victim_count
        or old.loss_amount is distinct from new.loss_amount
        or old.new_tactic is distinct from new.new_tactic
        or old.new_channel is distinct from new.new_channel
        or old.new_target is distinct from new.new_target
        or old.new_script is distinct from new.new_script
        or old.is_material_update is distinct from new.is_material_update
        or old.acceptance_status is distinct from new.acceptance_status
        or old.accepted_by is distinct from new.accepted_by
        or old.accepted_at is distinct from new.accepted_at
        or old.acceptance_path is distinct from new.acceptance_path
        or old.acceptance_policy_decision_id is distinct from new.acceptance_policy_decision_id
        or old.created_at is distinct from new.created_at
    ) then
        raise exception using errcode = '55000', message = 'resolved_evidence_is_immutable';
    end if;

    return new;
end;
$$;

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
        accepted_at = now(),
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
begin
    perform private.assert_live_policy_execution(
        p_policy_decision_id,
        p_pattern_id,
        p_pattern_revision_id
    );

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
        accepted_at = now(),
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
end;
$$;

create or replace function private.approve_review_item(
    p_expected_review_type text,
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
    actor_id uuid := auth.uid();
    exception_policy_decision_id uuid := private.current_human_exception_policy_id();
    queue_item public.review_items%rowtype;
    pattern public.scam_patterns%rowtype;
    revision public.pattern_revisions%rowtype;
    event_id uuid;
    verification_time timestamptz := now();
begin
    perform private.assert_enabled_admin(actor_id);

    if btrim(coalesce(p_decision_note, '')) = '' then
        raise exception using errcode = '23514', message = 'decision_note_required';
    end if;

    select * into queue_item
    from public.review_items
    where id = p_review_item_id
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'review_item_not_found';
    end if;

    if queue_item.review_type <> p_expected_review_type
       or queue_item.status not in ('pending', 'in_review', 'needs_evidence') then
        raise exception using errcode = '23514', message = 'review_item_not_approvable';
    end if;

    if queue_item.candidate_hash is distinct from p_expected_candidate_hash then
        raise exception using errcode = '40001', message = 'candidate_changed';
    end if;

    select * into pattern
    from public.scam_patterns
    where id = queue_item.target_id
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'pattern_not_found';
    end if;

    if pattern.row_version <> p_expected_row_version
       or queue_item.base_row_version <> p_expected_row_version then
        raise exception using errcode = '40001', message = 'stale_row_version';
    end if;

    select * into revision
    from public.pattern_revisions
    where id = p_draft_revision_id
      and pattern_id = pattern.id
    for update;

    if not found or revision.revision_status <> 'draft' then
        raise exception using errcode = '23514', message = 'draft_revision_required';
    end if;

    if pattern.current_draft_revision_id is distinct from revision.id then
        raise exception using errcode = '40001', message = 'draft_revision_changed';
    end if;

    if revision.content_hash is distinct from p_expected_content_hash then
        raise exception using errcode = '40001', message = 'reviewed_content_changed';
    end if;

    if exception_policy_decision_id is null then
        raise exception using errcode = '42501', message = 'human_policy_exception_context_required';
    end if;

    perform private.assert_human_policy_exception(
        exception_policy_decision_id,
        queue_item.id,
        revision.id
    );

    perform private.apply_evidence_decisions(
        pattern.id,
        actor_id,
        p_accepted_evidence_ids,
        p_rejected_evidence_ids
    );

    event_id := private.append_review_event(
        actor_id,
        case when p_expected_review_type = 'new_pattern' then 'create_pattern' else 'approve_update' end,
        'pattern_revision',
        revision.id,
        jsonb_build_object(
            'review_item_id', queue_item.id,
            'pattern_id', pattern.id,
            'row_version', pattern.row_version,
            'revision_status', revision.revision_status,
            'policy_decision_id', exception_policy_decision_id
        )::text,
        jsonb_build_object(
            'review_item_id', queue_item.id,
            'pattern_id', pattern.id,
            'row_version', pattern.row_version + 1,
            'revision_status', 'approved',
            'verification_path', 'human',
            'content_hash', revision.content_hash,
            'policy_decision_id', exception_policy_decision_id
        )::text,
        p_decision_note
    );

    update public.pattern_revisions
    set revision_status = 'approved',
        approved_by = actor_id,
        approved_at = verification_time,
        verified_at = verification_time,
        verification_path = 'human',
        verification_policy_decision_id = exception_policy_decision_id,
        verification_review_event_id = event_id
    where id = revision.id;

    update public.scam_patterns
    set latest_approved_revision_id = revision.id,
        current_draft_revision_id = null,
        lifecycle_status = 'review_ready',
        row_version = row_version + 1
    where id = pattern.id;

    update public.review_items
    set status = 'approved',
        assigned_to = actor_id,
        decision_note = p_decision_note,
        resolved_at = verification_time
    where id = queue_item.id;

    insert into public.publication_changes (
        pattern_id,
        action,
        pattern_revision_id,
        requested_by,
        review_event_id,
        reason,
        request_path,
        policy_decision_id
    ) values (
        pattern.id,
        'publish',
        revision.id,
        actor_id,
        event_id,
        p_decision_note,
        'human',
        exception_policy_decision_id
    );

    return revision.id;
end;
$$;

create or replace function public.record_policy_decision(
    p_review_item_id uuid,
    p_pattern_revision_id uuid,
    p_surface text,
    p_policy_version text,
    p_policy_hash text,
    p_input_hash text,
    p_gate_version text,
    p_gate_outcome text,
    p_rules_outcome text,
    p_decision_outcome text,
    p_execution_mode text,
    p_publication_authorized boolean,
    p_model_confidence_downgrade boolean,
    p_reason_codes text[],
    p_pipeline_run_id uuid,
    p_model_confidence numeric default null
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    queue_item public.review_items%rowtype;
    revision public.pattern_revisions%rowtype;
    pattern public.scam_patterns%rowtype;
    existing_decision public.policy_decisions%rowtype;
    decision_id uuid;
begin
    perform private.assert_trusted_service();

    if p_publication_authorized and not exists (
        select 1
        from private.active_live_publication_policies() as active_policy
        where active_policy.policy_version = p_policy_version
          and active_policy.policy_hash = p_policy_hash
          and active_policy.gate_version = p_gate_version
    ) then
        raise exception using errcode = '42501', message = 'policy_live_publication_policy_inactive';
    end if;

    select * into queue_item
    from public.review_items
    where id = p_review_item_id;

    select * into revision
    from public.pattern_revisions
    where id = p_pattern_revision_id;

    select * into pattern
    from public.scam_patterns
    where id = revision.pattern_id;

    if queue_item.id is null
       or revision.id is null
       or pattern.id is null then
        raise exception using errcode = 'P0002', message = 'policy_decision_target_not_found';
    end if;

    select * into existing_decision
    from public.policy_decisions
    where pattern_revision_id = revision.id
      and review_item_id = queue_item.id
      and pipeline_run_id = p_pipeline_run_id
      and surface = p_surface
      and policy_version = p_policy_version
      and policy_hash = p_policy_hash
      and input_hash = p_input_hash
      and execution_mode = p_execution_mode;

    if found then
        if existing_decision.pattern_id is distinct from pattern.id
           or existing_decision.content_hash is distinct from revision.content_hash
           or existing_decision.evidence_set_hash is distinct from revision.evidence_set_hash
           or existing_decision.candidate_hash is distinct from queue_item.candidate_hash
           or existing_decision.base_row_version is distinct from queue_item.base_row_version
           or existing_decision.gate_version is distinct from p_gate_version
           or existing_decision.gate_outcome is distinct from p_gate_outcome
           or existing_decision.rules_outcome is distinct from p_rules_outcome
           or existing_decision.decision_outcome is distinct from p_decision_outcome
           or existing_decision.publication_authorized is distinct from p_publication_authorized
           or existing_decision.model_confidence is distinct from p_model_confidence
           or existing_decision.model_confidence_downgrade is distinct from p_model_confidence_downgrade
           or existing_decision.reason_codes is distinct from p_reason_codes then
            raise exception using errcode = '23514', message = 'policy_decision_replay_mismatch';
        end if;

        return existing_decision.id;
    end if;

    insert into public.policy_decisions (
        pattern_id,
        pattern_revision_id,
        review_item_id,
        pipeline_run_id,
        surface,
        policy_version,
        policy_hash,
        input_hash,
        content_hash,
        evidence_set_hash,
        candidate_hash,
        base_row_version,
        gate_version,
        gate_outcome,
        rules_outcome,
        decision_outcome,
        execution_mode,
        publication_authorized,
        model_confidence,
        model_confidence_downgrade,
        reason_codes
    ) values (
        pattern.id,
        revision.id,
        queue_item.id,
        p_pipeline_run_id,
        p_surface,
        p_policy_version,
        p_policy_hash,
        p_input_hash,
        revision.content_hash,
        revision.evidence_set_hash,
        queue_item.candidate_hash,
        queue_item.base_row_version,
        p_gate_version,
        p_gate_outcome,
        p_rules_outcome,
        p_decision_outcome,
        p_execution_mode,
        p_publication_authorized,
        p_model_confidence,
        p_model_confidence_downgrade,
        p_reason_codes
    )
    on conflict on constraint policy_decisions_behavior_unique do nothing
    returning id into decision_id;

    if decision_id is null then
        select * into existing_decision
        from public.policy_decisions
        where pattern_revision_id = revision.id
          and review_item_id = queue_item.id
          and pipeline_run_id = p_pipeline_run_id
          and surface = p_surface
          and policy_version = p_policy_version
          and policy_hash = p_policy_hash
          and input_hash = p_input_hash
          and execution_mode = p_execution_mode;

        if existing_decision.id is null then
            raise exception using errcode = '40001', message = 'policy_decision_conflict_not_found';
        end if;

        if existing_decision.pattern_id is distinct from pattern.id
           or existing_decision.content_hash is distinct from revision.content_hash
           or existing_decision.evidence_set_hash is distinct from revision.evidence_set_hash
           or existing_decision.candidate_hash is distinct from queue_item.candidate_hash
           or existing_decision.base_row_version is distinct from queue_item.base_row_version
           or existing_decision.gate_version is distinct from p_gate_version
           or existing_decision.gate_outcome is distinct from p_gate_outcome
           or existing_decision.rules_outcome is distinct from p_rules_outcome
           or existing_decision.decision_outcome is distinct from p_decision_outcome
           or existing_decision.publication_authorized is distinct from p_publication_authorized
           or existing_decision.model_confidence is distinct from p_model_confidence
           or existing_decision.model_confidence_downgrade is distinct from p_model_confidence_downgrade
           or existing_decision.reason_codes is distinct from p_reason_codes then
            raise exception using errcode = '23514', message = 'policy_decision_replay_mismatch';
        end if;

        decision_id := existing_decision.id;
    end if;

    return decision_id;
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

    return private.approve_review_item(
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
end;
$$;

create or replace function public.apply_live_policy_publication(
    p_policy_decision_id uuid,
    p_expected_row_version bigint,
    p_expected_candidate_hash text,
    p_expected_content_hash text,
    p_accepted_evidence_ids uuid[],
    p_rejected_evidence_ids uuid[]
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    decision public.policy_decisions%rowtype;
    queue_item public.review_items%rowtype;
    pattern public.scam_patterns%rowtype;
    revision public.pattern_revisions%rowtype;
    verification_time timestamptz := now();
begin
    perform private.assert_trusted_service();

    select * into decision
    from public.policy_decisions
    where id = p_policy_decision_id
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'policy_decision_not_found';
    end if;

    select * into queue_item
    from public.review_items
    where id = decision.review_item_id
    for update;

    select * into pattern
    from public.scam_patterns
    where id = decision.pattern_id
    for update;

    select * into revision
    from public.pattern_revisions
    where id = decision.pattern_revision_id
    for update;

    perform set_config(
        'scam_radar.policy_execution_decision_id',
        decision.id::text,
        true
    );

    perform private.assert_live_policy_execution(
        decision.id,
        pattern.id,
        revision.id
    );

    if queue_item.status not in ('pending', 'in_review', 'needs_evidence')
       or revision.revision_status <> 'draft'
       or pattern.current_draft_revision_id is distinct from revision.id
       or pattern.row_version <> p_expected_row_version
       or queue_item.base_row_version <> p_expected_row_version
       or queue_item.candidate_hash is distinct from p_expected_candidate_hash
       or revision.content_hash is distinct from p_expected_content_hash then
        raise exception using errcode = '40001', message = 'live_policy_publication_input_changed';
    end if;

    perform private.apply_policy_evidence_decisions(
        decision.id,
        pattern.id,
        revision.id,
        p_accepted_evidence_ids,
        p_rejected_evidence_ids
    );

    update public.pattern_revisions
    set revision_status = 'approved',
        approved_by = null,
        approved_at = null,
        verified_at = verification_time,
        verification_path = 'policy',
        verification_policy_decision_id = decision.id,
        verification_review_event_id = null
    where id = revision.id;

    update public.scam_patterns
    set latest_approved_revision_id = revision.id,
        current_draft_revision_id = null,
        lifecycle_status = 'review_ready',
        row_version = row_version + 1
    where id = pattern.id;

    update public.review_items
    set status = 'approved',
        assigned_to = null,
        decision_note = 'policy_decision:' || decision.id::text,
        resolved_at = verification_time
    where id = queue_item.id;

    insert into public.publication_changes (
        pattern_id,
        action,
        pattern_revision_id,
        requested_by,
        review_event_id,
        reason,
        request_path,
        policy_decision_id
    ) values (
        pattern.id,
        'publish',
        revision.id,
        null,
        null,
        'policy_decision:' || decision.id::text,
        'policy',
        decision.id
    );

    return revision.id;
end;
$$;

create or replace function private.validate_release_item()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if not exists (
        select 1
        from public.public_releases
        where id = new.release_id
          and state = 'approved'
          and manifest_hash is null
    ) then
        raise exception using errcode = '55000', message = 'release_manifest_is_immutable';
    end if;

    if not exists (
        select 1
        from public.pattern_revisions
        where id = new.pattern_revision_id
          and pattern_id = new.pattern_id
          and revision_status = 'approved'
          and verified_at is not null
    ) then
        raise exception using errcode = '23514', message = 'release_requires_verified_revision';
    end if;

    if exists (
        select 1
        from public.public_releases as release
        join public.pattern_revisions as revision on revision.id = new.pattern_revision_id
        where release.id = new.release_id
          and release.schema_version = 2
          and (
              new.last_verified_at is null
              or revision.verified_at > release.published_at
              or new.last_verified_at > release.published_at
          )
    ) then
        raise exception using errcode = '23514', message = 'release_v2_verification_time_invalid';
    end if;

    if not exists (
        select 1
        from public.heat_snapshots
        where id = new.heat_snapshot_id
          and pattern_id = new.pattern_id
    ) then
        raise exception using errcode = '23514', message = 'release_heat_pattern_mismatch';
    end if;

    if new.last_verified_at is distinct from private.revision_last_verified_at(new.pattern_revision_id) then
        raise exception using errcode = '23514', message = 'release_last_verified_at_mismatch';
    end if;

    return new;
end;
$$;

create or replace function private.validate_release_evidence_item()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if not exists (
        select 1
        from public.public_releases as release
        where release.id = new.release_id
          and release.schema_version = 2
          and release.state = 'approved'
          and release.manifest_hash is null
          and new.last_verified_at <= release.published_at
    ) then
        raise exception using errcode = '55000', message = 'release_evidence_snapshot_not_writable_or_future_dated';
    end if;

    if not exists (
        select 1
        from public.public_release_items as item
        join public.evidence_claim_support as support
          on support.pattern_revision_id = item.pattern_revision_id
         and support.pattern_evidence_id = new.pattern_evidence_id
        join lateral private.revision_public_claims(item.pattern_revision_id) as claim
          on claim.field_path = support.field_path
         and claim.value_hash = support.value_hash
        join public.pattern_evidence as evidence
          on evidence.id = support.pattern_evidence_id
         and evidence.pattern_id = item.pattern_id
        where item.release_id = new.release_id
          and item.pattern_id = new.pattern_id
          and evidence.acceptance_status = 'accepted'
          and evidence.last_verified_at is not distinct from new.last_verified_at
    ) then
        raise exception using errcode = '23514', message = 'release_evidence_snapshot_mismatch';
    end if;

    return new;
end;
$$;

create trigger public_release_evidence_items_validate_insert
before insert on public.public_release_evidence_items
for each row execute function private.validate_release_evidence_item();

create trigger public_release_evidence_items_append_only
before update or delete on public.public_release_evidence_items
for each row execute function private.prevent_row_change();

create or replace function private.protect_public_release()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if tg_op = 'DELETE' then
        raise exception using errcode = '55000', message = 'public_releases_are_immutable';
    end if;

    if old.id is distinct from new.id
       or old.release_no is distinct from new.release_no
       or old.schema_version is distinct from new.schema_version
       or old.prepared_at is distinct from new.prepared_at
       or old.published_at is distinct from new.published_at
       or old.created_by is distinct from new.created_by then
        raise exception using errcode = '55000', message = 'public_release_identity_is_immutable';
    end if;

    if old.manifest_hash is not null and old.manifest_hash is distinct from new.manifest_hash then
        raise exception using errcode = '55000', message = 'public_release_manifest_is_immutable';
    end if;

    if old.manifest_hash is null and new.manifest_hash is not null and old.state <> 'approved' then
        raise exception using errcode = '55000', message = 'manifest_can_only_freeze_approved_release';
    end if;

    if old.artifact_hash is not null and old.artifact_hash is distinct from new.artifact_hash then
        raise exception using errcode = '55000', message = 'public_release_artifact_is_immutable';
    end if;

    if old.deployment_id is not null and old.deployment_id is distinct from new.deployment_id then
        raise exception using errcode = '55000', message = 'public_release_deployment_is_immutable';
    end if;

    if new.state = old.state then
        return new;
    end if;

    if not (
        (old.state = 'approved' and new.state in ('deploying', 'deploy_failed'))
        or (old.state = 'deploying' and new.state in ('deployed_unrecorded', 'deployed', 'deploy_failed'))
        or (old.state = 'deployed_unrecorded' and new.state in ('deployed', 'deploy_failed'))
        or (old.state = 'deploy_failed' and new.state = 'deploying')
        or (old.state = 'deployed' and new.state = 'superseded')
    ) then
        raise exception using errcode = '23514', message = 'invalid_release_state_transition';
    end if;

    return new;
end;
$$;

create or replace function private.protect_publication_change()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if tg_op = 'DELETE' then
        raise exception using errcode = '55000', message = 'publication_changes_are_append_only';
    end if;

    if old.id is distinct from new.id
       or old.pattern_id is distinct from new.pattern_id
       or old.action is distinct from new.action
       or old.pattern_revision_id is distinct from new.pattern_revision_id
       or old.requested_by is distinct from new.requested_by
       or old.review_event_id is distinct from new.review_event_id
       or old.request_path is distinct from new.request_path
       or old.policy_decision_id is distinct from new.policy_decision_id
       or old.reason is distinct from new.reason
       or old.created_at is distinct from new.created_at
       or old.applied_release_id is not null
       or new.applied_release_id is null then
        raise exception using errcode = '55000', message = 'publication_change_is_immutable';
    end if;

    return new;
end;
$$;

create or replace function private.validate_publication_change_request()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if new.request_path = 'human' then
        perform private.assert_enabled_admin(new.requested_by);

        if new.review_event_id is null or not exists (
            select 1
            from public.review_events
            where id = new.review_event_id
              and actor_id = new.requested_by
              and target_id in (new.pattern_id, new.pattern_revision_id)
        ) then
            raise exception using errcode = '23514', message = 'publication_request_requires_matching_review_event';
        end if;

        if new.action = 'publish' and not exists (
            select 1
            from public.pattern_revisions
            where id = new.pattern_revision_id
              and pattern_id = new.pattern_id
              and revision_status = 'approved'
              and verification_path = 'human'
              and approved_by = new.requested_by
              and verification_review_event_id = new.review_event_id
              and verification_policy_decision_id is not distinct from new.policy_decision_id
        ) then
            raise exception using errcode = '23514', message = 'publication_requires_human_verified_revision';
        end if;

        if new.action = 'unpublish' and not exists (
            select 1
            from public.scam_patterns
            where id = new.pattern_id
              and latest_approved_revision_id is not null
        ) then
            raise exception using errcode = '23514', message = 'unpublish_requires_approved_pattern';
        end if;
    elsif new.request_path = 'policy' then
        if new.action <> 'publish' then
            raise exception using errcode = '0A000', message = 'policy_unpublish_not_supported';
        end if;

        perform private.assert_live_policy_execution(
            new.policy_decision_id,
            new.pattern_id,
            new.pattern_revision_id
        );

        if not exists (
            select 1
            from public.pattern_revisions
            where id = new.pattern_revision_id
              and pattern_id = new.pattern_id
              and revision_status = 'approved'
              and verification_path = 'policy'
              and verification_policy_decision_id = new.policy_decision_id
              and approved_by is null
        ) then
            raise exception using errcode = '23514', message = 'publication_requires_policy_verified_revision';
        end if;
    else
        raise exception using errcode = '23514', message = 'publication_request_path_invalid';
    end if;

    return new;
end;
$$;

alter trigger publication_changes_require_human_request
on public.publication_changes
rename to publication_changes_require_authorized_request;

create or replace function public.prepare_public_release(p_expected_previous_release_id uuid default null)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    previous_release_id uuid;
    new_release_id uuid;
    release_published_at timestamptz := now();
    frozen_manifest_hash text;
begin
    perform private.assert_trusted_service();
    perform pg_advisory_xact_lock(hashtextextended('scam-radar-public-release', 0));
    lock table public.publication_changes in share row exclusive mode;
    lock table public.pattern_evidence in share mode;

    if exists (
        select 1
        from public.public_releases
        where state in ('approved', 'deploying', 'deployed_unrecorded', 'deploy_failed')
    ) then
        raise exception using errcode = '55000', message = 'release_already_pending';
    end if;

    select id into previous_release_id
    from public.public_releases
    where state = 'deployed'
    order by release_no desc
    limit 1;

    if p_expected_previous_release_id is distinct from previous_release_id then
        raise exception using errcode = '40001', message = 'deployed_release_changed';
    end if;

    if not exists (
        select 1 from public.publication_changes where applied_release_id is null
    ) then
        raise exception using errcode = 'P0002', message = 'no_pending_publication_changes';
    end if;

    if exists (
        with latest_change as (
            select distinct on (pattern_id) pattern_id, action, pattern_revision_id
            from public.publication_changes
            where applied_release_id is null
            order by pattern_id, created_at desc, id desc
        )
        select 1
        from latest_change
        where action = 'publish'
          and (
              not exists (
                  select 1 from public.pattern_revisions
                  where id = latest_change.pattern_revision_id
                    and pattern_id = latest_change.pattern_id
                    and revision_status = 'approved'
                    and verified_at is not null
              )
              or not exists (
                  select 1 from public.heat_snapshots
                  where pattern_id = latest_change.pattern_id
              )
          )
    ) then
        raise exception using errcode = '23514', message = 'release_change_not_exportable';
    end if;

    insert into public.public_releases (state, schema_version, published_at)
    values ('approved', 2, release_published_at)
    returning id into new_release_id;

    with changed_patterns as (
        select distinct pattern_id
        from public.publication_changes
        where applied_release_id is null
    )
    insert into public.public_release_items (
        release_id,
        pattern_id,
        pattern_revision_id,
        heat_snapshot_id,
        last_verified_at
    )
    select
        new_release_id,
        previous_item.pattern_id,
        previous_item.pattern_revision_id,
        previous_item.heat_snapshot_id,
        private.revision_last_verified_at(previous_item.pattern_revision_id)
    from public.public_release_items as previous_item
    where previous_item.release_id = previous_release_id
      and not exists (
          select 1 from changed_patterns where changed_patterns.pattern_id = previous_item.pattern_id
      );

    with latest_change as (
        select distinct on (pattern_id) pattern_id, action, pattern_revision_id
        from public.publication_changes
        where applied_release_id is null
        order by pattern_id, created_at desc, id desc
    )
    insert into public.public_release_items (
        release_id,
        pattern_id,
        pattern_revision_id,
        heat_snapshot_id,
        last_verified_at
    )
    select
        new_release_id,
        latest_change.pattern_id,
        latest_change.pattern_revision_id,
        heat.id,
        private.revision_last_verified_at(latest_change.pattern_revision_id)
    from latest_change
    cross join lateral (
        select snapshot.id
        from public.heat_snapshots as snapshot
        where snapshot.pattern_id = latest_change.pattern_id
        order by snapshot.as_of desc, snapshot.calculated_at desc, snapshot.id desc
        limit 1
    ) as heat
    where latest_change.action = 'publish';

    insert into public.public_release_evidence_items (
        release_id,
        pattern_id,
        pattern_evidence_id,
        last_verified_at
    )
    select distinct
        new_release_id,
        item.pattern_id,
        evidence.id,
        evidence.last_verified_at
    from public.public_release_items as item
    cross join lateral private.revision_public_claims(item.pattern_revision_id) as claim
    join public.evidence_claim_support as support
      on support.pattern_revision_id = item.pattern_revision_id
     and support.field_path = claim.field_path
     and support.value_hash = claim.value_hash
    join public.pattern_evidence as evidence
      on evidence.id = support.pattern_evidence_id
     and evidence.pattern_id = item.pattern_id
    where item.release_id = new_release_id
      and evidence.acceptance_status = 'accepted';

    if exists (
        select 1
        from public.public_release_items as item
        where item.release_id = new_release_id
          and item.last_verified_at is distinct from (
              select case
                  when count(*) = 0 then null
                  when count(snapshot.last_verified_at) <> count(*) then null
                  else min(snapshot.last_verified_at)
              end
              from public.public_release_evidence_items as snapshot
              where snapshot.release_id = item.release_id
                and snapshot.pattern_id = item.pattern_id
          )
    ) then
        raise exception using errcode = '40001', message = 'release_freshness_snapshot_changed';
    end if;

    select encode(
        extensions.digest(
            convert_to(
                'schema_version=2'
                || E'\npublished_at='
                || to_char(
                    release_published_at at time zone 'UTC',
                    'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                )
                || E'\nitems='
                || coalesce((
                    select string_agg(
                        item.pattern_id::text
                        || ':' || item.pattern_revision_id::text
                        || ':' || item.heat_snapshot_id::text
                        || ':' || coalesce(
                            to_char(
                                item.last_verified_at at time zone 'UTC',
                                'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                            ),
                            'unknown'
                        ),
                        '|' order by item.pattern_id
                    )
                    from public.public_release_items as item
                    where item.release_id = new_release_id
                ), '')
                || E'\nevidence='
                || coalesce((
                    select string_agg(
                        snapshot.pattern_id::text
                        || ':' || snapshot.pattern_evidence_id::text
                        || ':' || coalesce(
                            to_char(
                                snapshot.last_verified_at at time zone 'UTC',
                                'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'
                            ),
                            'unknown'
                        ),
                        '|' order by snapshot.pattern_id, snapshot.pattern_evidence_id
                    )
                    from public.public_release_evidence_items as snapshot
                    where snapshot.release_id = new_release_id
                ), ''),
                'UTF8'
            ),
            'sha256'
        ),
        'hex'
    ) into frozen_manifest_hash;

    update public.public_releases
    set manifest_hash = frozen_manifest_hash
    where id = new_release_id;

    update public.publication_changes
    set applied_release_id = new_release_id
    where applied_release_id is null;

    return new_release_id;
end;
$$;

create or replace function private.export_public_release_v1(p_release_id uuid)
returns jsonb
language sql
stable
security invoker
set search_path = ''
set timezone = 'UTC'
as $$
    select jsonb_build_object(
        'schema_version', 'public-release-v1',
        'release_id', release.id,
        'release_no', release.release_no,
        'manifest_hash', release.manifest_hash,
        'prepared_at', release.prepared_at,
        'patterns', coalesce((
            select jsonb_agg(
                jsonb_build_object(
                    'pattern_id', item.pattern_id,
                    'revision_id', revision.id,
                    'slug', pattern.slug,
                    'canonical_name', revision.canonical_name,
                    'short_name', revision.short_name,
                    'pattern_type', revision.pattern_type,
                    'risk_type', revision.risk_type,
                    'evidence_level', revision.evidence_level,
                    'legal_status', revision.legal_status,
                    'public_evidence_label', revision.public_evidence_label,
                    'one_sentence_summary', revision.one_sentence_summary,
                    'target_population', revision.target_population,
                    'contact_channels', revision.contact_channels,
                    'impersonated_identities', revision.impersonated_identities,
                    'hooks', revision.hooks,
                    'common_phrases', revision.common_phrases,
                    'pressure_tactics', revision.pressure_tactics,
                    'requested_actions', revision.requested_actions,
                    'money_paths', revision.money_paths,
                    'technology_used', revision.technology_used,
                    'warning_signs', revision.warning_signs,
                    'what_to_do', revision.what_to_do,
                    'regions', revision.regions,
                    'first_seen_at', revision.first_seen_at,
                    'last_seen_at', revision.last_seen_at,
                    'last_material_change_at', revision.last_material_change_at,
                    'last_reviewed_at', revision.approved_at,
                    'aliases', coalesce((
                        select jsonb_agg(alias.alias order by alias.normalized_alias, alias.id)
                        from public.scam_aliases as alias
                        where alias.pattern_revision_id = revision.id
                    ), '[]'::jsonb),
                    'evidence', coalesce((
                        select jsonb_agg(
                            jsonb_build_object(
                                'evidence_id', evidence.id,
                                'source_name', source.name,
                                'source_type', source.source_type,
                                'authority_tier', source.authority_tier,
                                'title', version.title,
                                'url', version.canonical_url,
                                'published_at', version.published_at,
                                'event_date', evidence.event_date,
                                'region', evidence.region,
                                'claim_summary', evidence.claim_summary
                            ) order by coalesce(evidence.event_date, version.published_at::date) desc, evidence.id
                        )
                        from (
                            select distinct support.pattern_evidence_id
                            from public.evidence_claim_support as support
                            where support.pattern_revision_id = revision.id
                        ) as supported
                        join public.pattern_evidence as evidence on evidence.id = supported.pattern_evidence_id
                        join public.source_item_versions as version on version.id = evidence.source_item_version_id
                        join public.source_items as source_item on source_item.id = version.source_item_id
                        join public.sources as source on source.id = source_item.source_id
                        where evidence.acceptance_status = 'accepted'
                    ), '[]'::jsonb),
                    'heat', jsonb_build_object(
                        'snapshot_id', heat.id,
                        'score_version', heat.score_version,
                        'as_of', heat.as_of,
                        'score', heat.score,
                        'breakdown', heat.breakdown,
                        'input_hash', heat.input_hash
                    )
                ) order by heat.score desc, revision.canonical_name, item.pattern_id
            )
            from public.public_release_items as item
            join public.scam_patterns as pattern on pattern.id = item.pattern_id
            join public.pattern_revisions as revision on revision.id = item.pattern_revision_id
            join public.heat_snapshots as heat on heat.id = item.heat_snapshot_id
            where item.release_id = release.id
        ), '[]'::jsonb)
    )
    from public.public_releases as release
    where release.id = p_release_id;
$$;

create or replace function public.export_public_release(p_release_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
set timezone = 'UTC'
as $$
declare
    target_release public.public_releases%rowtype;
    release_payload jsonb;
begin
    perform private.assert_trusted_service();

    select * into target_release
    from public.public_releases
    where id = p_release_id
      and manifest_hash is not null
      and state in ('approved', 'deploying', 'deployed_unrecorded', 'deployed', 'superseded');

    if not found then
        raise exception using errcode = '23514', message = 'release_not_exportable';
    end if;

    if target_release.schema_version = 1 then
        return private.export_public_release_v1(target_release.id);
    end if;

    select jsonb_build_object(
        'schema_version', 2,
        'release_id', release.id,
        'release_no', release.release_no,
        'manifest_hash', release.manifest_hash,
        'generated_at', release.prepared_at,
        'published_at', release.published_at,
        'as_of', (
            select max(heat.as_of)
            from public.public_release_items as as_of_item
            join public.heat_snapshots as heat on heat.id = as_of_item.heat_snapshot_id
            where as_of_item.release_id = release.id
        ),
        'patterns', coalesce((
            select jsonb_agg(
                jsonb_build_object(
                    'id', item.pattern_id,
                    'revision_id', revision.id,
                    'slug', pattern.slug,
                    'canonical_name', revision.canonical_name,
                    'short_name', revision.short_name,
                    'pattern_type', revision.pattern_type,
                    'risk_type', revision.risk_type,
                    'evidence_level', revision.evidence_level,
                    'legal_status', revision.legal_status,
                    'evidence_label', revision.public_evidence_label,
                    'one_sentence_summary', revision.one_sentence_summary,
                    'target_population', revision.target_population,
                    'contact_channels', revision.contact_channels,
                    'impersonated_identities', revision.impersonated_identities,
                    'hooks', revision.hooks,
                    'common_phrases', revision.common_phrases,
                    'pressure_tactics', revision.pressure_tactics,
                    'requested_actions', revision.requested_actions,
                    'money_paths', revision.money_paths,
                    'technology_used', revision.technology_used,
                    'warning_signs', revision.warning_signs,
                    'what_to_do', revision.what_to_do,
                    'regions', revision.regions,
                    'first_seen_at', revision.first_seen_at,
                    'last_seen_at', revision.last_seen_at,
                    'last_material_change_at', revision.last_material_change_at,
                    'verified_at', revision.verified_at,
                    'last_verified_at', item.last_verified_at,
                    'aliases', coalesce((
                        select jsonb_agg(alias.alias order by alias.normalized_alias, alias.id)
                        from public.scam_aliases as alias
                        where alias.pattern_revision_id = revision.id
                    ), '[]'::jsonb),
                    'evidence', coalesce((
                        select jsonb_agg(
                            jsonb_build_object(
                                'evidence_id', evidence.id,
                                'institution', source.name,
                                'source_type', source.source_type,
                                'authority_tier', source.authority_tier,
                                'title', version.title,
                                'url', version.canonical_url,
                                'published_at', version.published_at,
                                'date', coalesce(evidence.event_date, version.published_at::date),
                                'region', evidence.region,
                                'last_verified_at', snapshot.last_verified_at,
                                'claim_summary', evidence.claim_summary
                            ) order by coalesce(evidence.event_date, version.published_at::date) desc, evidence.id
                        )
                        from public.public_release_evidence_items as snapshot
                        join public.pattern_evidence as evidence
                          on evidence.id = snapshot.pattern_evidence_id
                         and evidence.pattern_id = snapshot.pattern_id
                        join public.source_item_versions as version on version.id = evidence.source_item_version_id
                        join public.source_items as source_item on source_item.id = version.source_item_id
                        join public.sources as source on source.id = source_item.source_id
                        where snapshot.release_id = item.release_id
                          and snapshot.pattern_id = item.pattern_id
                    ), '[]'::jsonb),
                    'heat', jsonb_build_object(
                        'snapshot_id', heat.id,
                        'score_version', heat.score_version,
                        'as_of', heat.as_of,
                        'score', heat.score,
                        'breakdown', heat.breakdown,
                        'input_hash', heat.input_hash
                    )
                ) order by heat.score desc, revision.canonical_name, item.pattern_id
            )
            from public.public_release_items as item
            join public.scam_patterns as pattern on pattern.id = item.pattern_id
            join public.pattern_revisions as revision on revision.id = item.pattern_revision_id
            join public.heat_snapshots as heat on heat.id = item.heat_snapshot_id
            where item.release_id = release.id
        ), '[]'::jsonb)
    ) into release_payload
    from public.public_releases as release
    where release.id = target_release.id;

    return release_payload;
end;
$$;

revoke execute on function public.record_policy_decision(
    uuid, uuid, text, text, text, text, text, text, text, text, text, boolean, boolean, text[], uuid, numeric
) from public, anon, authenticated;
grant execute on function public.record_policy_decision(
    uuid, uuid, text, text, text, text, text, text, text, text, text, boolean, boolean, text[], uuid, numeric
) to service_role;

revoke execute on function public.confirm_policy_publication(
    uuid, uuid, uuid, bigint, text, text, uuid[], uuid[], text
) from public, anon, service_role;
grant execute on function public.confirm_policy_publication(
    uuid, uuid, uuid, bigint, text, text, uuid[], uuid[], text
) to authenticated;

revoke execute on function public.apply_live_policy_publication(
    uuid, bigint, text, text, uuid[], uuid[]
) from public, anon, authenticated;
grant execute on function public.apply_live_policy_publication(
    uuid, bigint, text, text, uuid[], uuid[]
) to service_role;

revoke execute on function public.approve_new_pattern(
    uuid, uuid, bigint, text, text, uuid[], uuid[], text
) from public, anon, authenticated, service_role;

revoke execute on function public.approve_pattern_update(
    uuid, uuid, bigint, text, text, uuid[], uuid[], text
) from public, anon, authenticated, service_role;

commit;
