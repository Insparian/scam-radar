begin;

-- A Pages upload can fail smoke before the new release becomes the database
-- active pointer. Keep both receipts and close that attempt only after Pages
-- has restored the previously active artifact.

alter table public.public_releases
drop constraint public_releases_state_check;
alter table public.public_releases
add constraint public_releases_state_check check (
    state in (
        'approved', 'deploying', 'deployed_unrecorded', 'deployed',
        'deploy_failed', 'superseded', 'upload_rolled_back'
    )
);

alter table private.deployment_receipts
drop constraint deployment_receipts_action_check;
alter table private.deployment_receipts
add constraint deployment_receipts_action_check check (
    action in ('publish', 'rollback', 'withdraw_uploaded')
);

-- The same original Pages deployment may be restored after multiple distinct
-- failed uploads. Event IDs and RPC state checks provide idempotence; this
-- tuple is not a unique event identity.
alter table private.deployment_receipts
drop constraint deployment_receipts_release_id_deployment_id_action_key;

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
        or (old.state = 'deployed_unrecorded' and new.state in ('deployed', 'upload_rolled_back'))
        or (old.state = 'deploy_failed' and new.state = 'deploying')
        or (old.state = 'deployed' and new.state = 'superseded')
        or (old.state = 'superseded' and new.state = 'deployed')
    ) then
        raise exception using errcode = '23514', message = 'invalid_release_state_transition';
    end if;
    return new;
end;
$$;

create or replace function public.record_unrecorded_upload_rollback(
    p_failed_release_id uuid,
    p_failed_deployment_id text,
    p_expected_active_release_id uuid,
    p_expected_active_deployment_id text,
    p_restored_deployment_id text,
    p_restored_artifact_hash text,
    p_reason_code text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
    failed public.public_releases%rowtype;
    active public.public_releases%rowtype;
    current_state private.deployment_state%rowtype;
begin
    perform private.assert_trusted_service();
    perform pg_advisory_xact_lock(hashtextextended('scam-radar-public-deployment', 0));
    select * into current_state from private.deployment_state where singleton for update;
    select * into failed from public.public_releases where id = p_failed_release_id for update;
    select * into active from public.public_releases where id = p_expected_active_release_id for update;
    if failed.id is null or active.id is null then
        raise exception using errcode = 'P0002', message = 'release_not_found';
    end if;
    if failed.deployment_id is distinct from p_failed_deployment_id
       or failed.release_no <= active.release_no
       or nullif(btrim(coalesce(p_restored_deployment_id, '')), '') is null
       or nullif(btrim(coalesce(p_failed_deployment_id, '')), '') is null
       or current_state.active_artifact_hash is distinct from p_restored_artifact_hash
       or coalesce(p_reason_code, '') !~ '^[a-z0-9_]{1,100}$' then
        raise exception using errcode = '23514', message = 'unrecorded_rollback_receipt_invalid';
    end if;
    if failed.state = 'upload_rolled_back'
       and current_state.active_release_id = active.id
       and current_state.active_deployment_id = p_restored_deployment_id
       and exists (
           select 1 from private.deployment_receipts
           where release_id=failed.id and deployment_id=p_failed_deployment_id
             and action='withdraw_uploaded' and reason_code=p_reason_code
       ) and exists (
           select 1 from private.deployment_receipts
           where release_id=active.id and deployment_id=p_restored_deployment_id
             and artifact_hash=p_restored_artifact_hash and action='rollback'
             and reason_code=p_reason_code
       ) then
        return;
    end if;
    if current_state.active_release_id is distinct from active.id
       or current_state.active_deployment_id is distinct from p_expected_active_deployment_id
       or active.state <> 'deployed' then
        raise exception using errcode = '40001', message = 'active_deployment_changed';
    end if;
    if failed.state <> 'deployed_unrecorded' then
        raise exception using errcode = '23514', message = 'unrecorded_rollback_receipt_invalid';
    end if;
    insert into private.deployment_receipts (
        release_id, deployment_id, artifact_hash, action,
        previous_release_id, previous_deployment_id, reason_code
    ) values (
        failed.id, p_failed_deployment_id, failed.artifact_hash, 'withdraw_uploaded',
        active.id, p_expected_active_deployment_id, p_reason_code
    );
    insert into private.deployment_receipts (
        release_id, deployment_id, artifact_hash, action,
        previous_release_id, previous_deployment_id, reason_code
    ) values (
        active.id, p_restored_deployment_id, p_restored_artifact_hash, 'rollback',
        failed.id, p_failed_deployment_id, p_reason_code
    );
    update public.public_releases
    set state = 'upload_rolled_back', redacted_error = p_reason_code
    where id = failed.id;
    update private.deployment_state
    set active_deployment_id = p_restored_deployment_id, updated_at = now()
    where singleton;
end;
$$;

revoke execute on function public.record_unrecorded_upload_rollback(
    uuid, text, uuid, text, text, text, text
) from public, anon, authenticated;
grant execute on function public.record_unrecorded_upload_rollback(
    uuid, text, uuid, text, text, text, text
) to service_role;

commit;
