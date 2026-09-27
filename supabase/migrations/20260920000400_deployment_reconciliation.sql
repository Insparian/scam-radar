begin;

-- Keep immutable release contents separate from the current Pages deployment.
-- A rollback can make an older, already verified artifact live again without
-- rewriting its first upload receipt or any release manifest.

create table private.deployment_state (
    singleton boolean primary key default true check (singleton),
    active_release_id uuid references public.public_releases(id) on delete restrict,
    active_deployment_id text,
    active_artifact_hash text check (
        active_artifact_hash is null or active_artifact_hash ~ '^[0-9a-f]{64}$'
    ),
    updated_at timestamptz not null default now(),
    constraint deployment_state_complete check (
        (active_release_id is null and active_deployment_id is null and active_artifact_hash is null)
        or (active_release_id is not null and nullif(btrim(active_deployment_id), '') is not null
            and active_artifact_hash is not null)
    )
);

insert into private.deployment_state (
    singleton, active_release_id, active_deployment_id, active_artifact_hash
)
select true, deployed.id, deployed.deployment_id, deployed.artifact_hash
from public.public_releases as deployed
where deployed.state = 'deployed'
order by deployed.release_no desc
limit 1;

insert into private.deployment_state (singleton)
values (true)
on conflict (singleton) do nothing;

create table private.deployment_receipts (
    id uuid primary key default extensions.gen_random_uuid(),
    release_id uuid not null references public.public_releases(id) on delete restrict,
    deployment_id text not null check (nullif(btrim(deployment_id), '') is not null),
    artifact_hash text not null check (artifact_hash ~ '^[0-9a-f]{64}$'),
    action text not null check (action in ('publish', 'rollback')),
    previous_release_id uuid references public.public_releases(id) on delete restrict,
    previous_deployment_id text,
    reason_code text not null check (char_length(reason_code) between 1 and 100),
    recorded_at timestamptz not null default now(),
    unique (release_id, deployment_id, action)
);

insert into private.deployment_receipts (
    release_id, deployment_id, artifact_hash, action, reason_code
)
select id, deployment_id, artifact_hash, 'publish', 'pre_migration_active'
from public.public_releases
where state = 'deployed';

alter table private.deployment_state enable row level security;
alter table private.deployment_receipts enable row level security;
revoke all on private.deployment_state, private.deployment_receipts
from public, anon, authenticated, service_role;

create trigger deployment_receipts_append_only
before update or delete on private.deployment_receipts
for each row execute function private.prevent_row_change();

-- The first deployment_id on a release remains immutable. The current Pages
-- receipt is held in deployment_state and append-only deployment_receipts.
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
        or (old.state = 'deployed_unrecorded' and new.state = 'deployed')
        or (old.state = 'deploy_failed' and new.state = 'deploying')
        or (old.state = 'deployed' and new.state = 'superseded')
        or (old.state = 'superseded' and new.state = 'deployed')
    ) then
        raise exception using errcode = '23514', message = 'invalid_release_state_transition';
    end if;
    return new;
end;
$$;

create or replace function public.note_release_uploaded(
    p_release_id uuid,
    p_deployment_id text,
    p_artifact_hash text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    target public.public_releases%rowtype;
begin
    perform private.assert_trusted_service();
    perform pg_advisory_xact_lock(hashtextextended('scam-radar-public-deployment', 0));
    select * into target from public.public_releases where id = p_release_id for update;
    if not found then
        raise exception using errcode = 'P0002', message = 'release_not_found';
    end if;
    if nullif(btrim(coalesce(p_deployment_id, '')), '') is null
       or target.artifact_hash is distinct from p_artifact_hash then
        raise exception using errcode = '23514', message = 'deployment_receipt_mismatch';
    end if;
    if target.state = 'deployed_unrecorded' and target.deployment_id = p_deployment_id then
        return;
    end if;
    if target.state <> 'deploying' or target.deployment_id is not null then
        raise exception using errcode = '23514', message = 'release_upload_not_recordable';
    end if;
    if exists (
        select 1 from public.public_releases
        where state = 'deployed' and release_no > target.release_no
    ) then
        raise exception using errcode = '55000', message = 'older_release_cannot_overwrite_newer';
    end if;
    update public.public_releases
    set state = 'deployed_unrecorded', deployment_id = p_deployment_id
    where id = p_release_id;
end;
$$;

create or replace function public.record_deployed_release(
    p_release_id uuid,
    p_deployment_id text,
    p_artifact_hash text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    target public.public_releases%rowtype;
    current_state private.deployment_state%rowtype;
begin
    perform private.assert_trusted_service();
    perform pg_advisory_xact_lock(hashtextextended('scam-radar-public-deployment', 0));
    select * into target from public.public_releases where id = p_release_id for update;
    select * into current_state from private.deployment_state where singleton for update;
    if target.id is null then
        raise exception using errcode = 'P0002', message = 'release_not_found';
    end if;
    if nullif(btrim(coalesce(p_deployment_id, '')), '') is null
       or target.artifact_hash is distinct from p_artifact_hash
       or (target.deployment_id is not null and target.deployment_id <> p_deployment_id) then
        raise exception using errcode = '23514', message = 'deployment_record_mismatch';
    end if;
    if target.state = 'deployed' then
        if current_state.active_release_id = p_release_id
           and current_state.active_deployment_id = p_deployment_id then
            return;
        end if;
        raise exception using errcode = '23514', message = 'deployment_state_diverged';
    end if;
    if target.state not in ('deploying', 'deployed_unrecorded') then
        raise exception using errcode = '23514', message = 'deployment_record_mismatch';
    end if;
    if exists (
        select 1 from public.public_releases
        where state = 'deployed' and release_no > target.release_no
    ) then
        raise exception using errcode = '55000', message = 'older_release_cannot_overwrite_newer';
    end if;
    update public.public_releases
    set state = 'superseded', superseded_at = now()
    where state = 'deployed' and id <> p_release_id;
    update public.public_releases
    set state = 'deployed', deployment_id = p_deployment_id,
        deployed_at = now(), previous_deployment_id = current_state.active_deployment_id,
        redacted_error = null
    where id = p_release_id;
    insert into private.deployment_receipts (
        release_id, deployment_id, artifact_hash, action,
        previous_release_id, previous_deployment_id, reason_code
    ) values (
        p_release_id, p_deployment_id, p_artifact_hash, 'publish',
        current_state.active_release_id, current_state.active_deployment_id, 'release_published'
    );
    update private.deployment_state
    set active_release_id = p_release_id, active_deployment_id = p_deployment_id,
        active_artifact_hash = p_artifact_hash, updated_at = now()
    where singleton;
end;
$$;

create or replace function public.record_release_failure(
    p_release_id uuid,
    p_redacted_error text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    perform private.assert_trusted_service();
    if btrim(coalesce(p_redacted_error, '')) = '' or char_length(p_redacted_error) > 500 then
        raise exception using errcode = '22023', message = 'invalid_redacted_error';
    end if;
    update public.public_releases
    set state = 'deploy_failed', redacted_error = p_redacted_error
    where id = p_release_id and state in ('approved', 'deploying');
    if not found then
        raise exception using errcode = '23514', message = 'release_failure_not_recordable';
    end if;
end;
$$;

create or replace function public.record_release_rollback(
    p_target_release_id uuid,
    p_expected_active_release_id uuid,
    p_expected_active_deployment_id text,
    p_rollback_deployment_id text,
    p_artifact_hash text,
    p_reason_code text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    target public.public_releases%rowtype;
    current_state private.deployment_state%rowtype;
begin
    perform private.assert_trusted_service();
    perform pg_advisory_xact_lock(hashtextextended('scam-radar-public-deployment', 0));
    select * into current_state from private.deployment_state where singleton for update;
    select * into target from public.public_releases where id = p_target_release_id for update;
    if target.id is null then
        raise exception using errcode = 'P0002', message = 'release_not_found';
    end if;
    if nullif(btrim(coalesce(p_rollback_deployment_id, '')), '') is null
       or coalesce(p_reason_code, '') !~ '^[a-z0-9_]{1,100}$'
       or target.artifact_hash is distinct from p_artifact_hash then
        raise exception using errcode = '23514', message = 'rollback_receipt_invalid';
    end if;
    if current_state.active_release_id = p_target_release_id
       and current_state.active_deployment_id = p_rollback_deployment_id then
        return;
    end if;
    if current_state.active_release_id is distinct from p_expected_active_release_id
       or current_state.active_deployment_id is distinct from p_expected_active_deployment_id then
        raise exception using errcode = '40001', message = 'active_deployment_changed';
    end if;
    if target.state <> 'superseded' or target.deployed_at is null
       or not exists (
           select 1 from public.public_releases as active
           where active.id = current_state.active_release_id
             and active.state = 'deployed'
             and active.release_no > target.release_no
       ) then
        raise exception using errcode = '23514', message = 'rollback_target_not_prior_deployment';
    end if;
    update public.public_releases
    set state = 'superseded', superseded_at = now()
    where id = current_state.active_release_id;
    update public.public_releases
    set state = 'deployed', superseded_at = null
    where id = p_target_release_id;
    insert into private.deployment_receipts (
        release_id, deployment_id, artifact_hash, action,
        previous_release_id, previous_deployment_id, reason_code
    ) values (
        p_target_release_id, p_rollback_deployment_id, p_artifact_hash, 'rollback',
        current_state.active_release_id, current_state.active_deployment_id, p_reason_code
    );
    update private.deployment_state
    set active_release_id = p_target_release_id,
        active_deployment_id = p_rollback_deployment_id,
        active_artifact_hash = p_artifact_hash, updated_at = now()
    where singleton;
end;
$$;

revoke execute on function public.note_release_uploaded(uuid, text, text) from public, anon, authenticated;
revoke execute on function public.record_release_rollback(uuid, uuid, text, text, text, text) from public, anon, authenticated;
grant execute on function public.note_release_uploaded(uuid, text, text) to service_role;
grant execute on function public.record_release_rollback(uuid, uuid, text, text, text, text) to service_role;

commit;
