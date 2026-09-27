-- Appended inside the existing synthetic review/release contract transaction.
-- No upload occurs; these are the real database lifecycle RPCs.
do $$
declare
    target uuid;
    newer uuid;
    version bigint;
begin
    select release_id into target from local_contract_context;
    perform public.mark_release_deploying(target, repeat('d',64), repeat('e',40));
    begin
        perform public.record_deployed_release(target, 'local-protocol-upload', repeat('f',64));
        raise exception 'wrong_artifact_was_recorded';
    exception when check_violation then
        if sqlerrm <> 'deployment_record_mismatch' then raise; end if;
    end;
    if not exists(select 1 from public.public_releases where id=target and state='deploying') then
        raise exception 'failed_registration_corrupted_release';
    end if;
    begin
        perform public.note_release_uploaded(target, 'local-protocol-upload', repeat('f',64));
        raise exception 'wrong_upload_receipt_accepted';
    exception when check_violation then
        if sqlerrm <> 'deployment_receipt_mismatch' then raise; end if;
    end;
    perform public.note_release_uploaded(target, 'local-protocol-upload', repeat('d',64));
    perform public.note_release_uploaded(target, 'local-protocol-upload', repeat('d',64));
    if not exists(select 1 from public.public_releases where id=target and state='deployed_unrecorded') then
        raise exception 'uploaded_unrecorded_state_missing';
    end if;
    begin
        perform public.record_release_failure(target, 'cannot_call_uploaded_a_build_failure');
        raise exception 'uploaded_release_was_falsely_marked_failed';
    exception when check_violation then
        if sqlerrm <> 'release_failure_not_recordable' then raise; end if;
    end;
    perform public.record_deployed_release(target, 'local-protocol-upload', repeat('d',64));
    perform public.record_deployed_release(target, 'local-protocol-upload', repeat('d',64));
    if not exists (
        select 1 from private.deployment_state
        where active_release_id=target and active_deployment_id='local-protocol-upload'
    ) then
        raise exception 'initial_active_deployment_missing';
    end if;
    -- A human takedown creates a second immutable release through real RPCs.
    perform set_config('request.jwt.claims', '{"role":"authenticated","sub":"eeeeeeee-0000-4000-8000-000000000001"}', true);
    perform set_config('request.jwt.claim.role', 'authenticated', true);
    select row_version into version from public.scam_patterns where id='50000000-0000-4000-8000-000000000001';
    perform public.unpublish_pattern('50000000-0000-4000-8000-000000000001', version, 'synthetic takedown');
    perform set_config('request.jwt.claims', '{"role":"service_role"}', true);
    perform set_config('request.jwt.claim.role', 'service_role', true);
    newer := public.prepare_public_release(target);
    perform public.mark_release_deploying(newer, repeat('a',64), repeat('e',40));
    perform public.record_release_failure(newer, 'local_build_failure');
    if not exists(select 1 from public.public_releases where id=target and state='deployed') then
        raise exception 'build_failure_replaced_current';
    end if;
    perform public.mark_release_deploying(newer, repeat('a',64), repeat('e',40));
    perform public.note_release_uploaded(newer, 'local-removal-upload', repeat('a',64));
    perform public.record_deployed_release(newer, 'local-removal-upload', repeat('a',64));
    begin
        perform public.mark_release_deploying(target, repeat('d',64), repeat('e',40));
        raise exception 'older_release_was_accepted';
    exception when object_not_in_prerequisite_state then
        if sqlerrm <> 'older_release_cannot_overwrite_newer' then raise; end if;
    end;
    begin
        perform public.record_release_rollback(
            target, newer, 'local-removal-upload', 'local-original-restored',
            repeat('f',64), 'synthetic_rollback'
        );
        raise exception 'wrong_rollback_artifact_accepted';
    exception when check_violation then
        if sqlerrm <> 'rollback_receipt_invalid' then raise; end if;
    end;
    begin
        perform public.record_release_rollback(
            target, target, 'local-removal-upload', 'local-original-restored',
            repeat('d',64), 'synthetic_rollback'
        );
        raise exception 'stale_rollback_expectation_accepted';
    exception when serialization_failure then
        if sqlerrm <> 'active_deployment_changed' then raise; end if;
    end;
    perform public.record_release_rollback(
        target, newer, 'local-removal-upload', 'local-original-restored',
        repeat('d',64), 'synthetic_rollback'
    );
    perform public.record_release_rollback(
        target, newer, 'local-removal-upload', 'local-original-restored',
        repeat('d',64), 'synthetic_rollback'
    );
    if not exists (
        select 1 from private.deployment_state
        where active_release_id=target
          and active_deployment_id='local-original-restored'
          and active_artifact_hash=repeat('d',64)
    ) or not exists (
        select 1 from public.public_releases where id=target and state='deployed'
    ) or not exists (
        select 1 from public.public_releases where id=newer and state='superseded'
    ) or (select count(*) from private.deployment_receipts where action='rollback') <> 1 then
        raise exception 'original_artifact_rollback_not_recorded';
    end if;
end;
$$;
\echo 'Deployment DB contract passed: unrecorded receipt, idempotent registration, failed build preservation, old release refusal, original artifact rollback.'

-- A later upload that fails public smoke before registration must be explicitly
-- withdrawn after Pages restores the previously active artifact.
do $$
declare
    original uuid;
    failed uuid;
    version bigint;
begin
    select release_id into original from local_contract_context;
    perform set_config('request.jwt.claims', '{"role":"authenticated","sub":"eeeeeeee-0000-4000-8000-000000000001"}', true);
    perform set_config('request.jwt.claim.role', 'authenticated', true);
    select row_version into version from public.scam_patterns where id='50000000-0000-4000-8000-000000000001';
    perform public.unpublish_pattern('50000000-0000-4000-8000-000000000001', version, 'second synthetic takedown');
    perform set_config('request.jwt.claims', '{"role":"service_role"}', true);
    perform set_config('request.jwt.claim.role', 'service_role', true);
    failed := public.prepare_public_release(original);
    perform public.mark_release_deploying(failed, repeat('b',64), repeat('e',40));
    perform public.note_release_uploaded(failed, 'local-smoke-failed-upload', repeat('b',64));
    begin
        perform public.record_unrecorded_upload_rollback(
            failed, 'local-smoke-failed-upload', original, 'local-original-restored',
            'local-original-restored', repeat('f',64), 'smoke_failed'
        );
        raise exception 'wrong_restored_artifact_accepted';
    exception when check_violation then
        if sqlerrm <> 'unrecorded_rollback_receipt_invalid' then raise; end if;
    end;
    begin
        perform public.record_unrecorded_upload_rollback(
            failed, 'local-smoke-failed-upload', original, 'stale-active-id',
            'local-original-restored', repeat('d',64), 'smoke_failed'
        );
        raise exception 'stale_unrecorded_rollback_accepted';
    exception when serialization_failure then
        if sqlerrm <> 'active_deployment_changed' then raise; end if;
    end;
    perform public.record_unrecorded_upload_rollback(
        failed, 'local-smoke-failed-upload', original, 'local-original-restored',
        'local-original-restored', repeat('d',64), 'smoke_failed'
    );
    begin
        perform public.record_unrecorded_upload_rollback(
            failed, 'local-smoke-failed-upload', original, 'local-original-restored',
            'local-original-restored', repeat('f',64), 'smoke_failed'
        );
        raise exception 'wrong_replay_hash_was_accepted';
    exception when check_violation then
        if sqlerrm <> 'unrecorded_rollback_receipt_invalid' then raise; end if;
    end;
    perform public.record_unrecorded_upload_rollback(
        failed, 'local-smoke-failed-upload', original, 'local-original-restored',
        'local-original-restored', repeat('d',64), 'smoke_failed'
    );
    if not exists (
        select 1 from public.public_releases
        where id=failed and state='upload_rolled_back' and redacted_error='smoke_failed'
    ) or not exists (
        select 1 from private.deployment_state
        where active_release_id=original and active_deployment_id='local-original-restored'
          and active_artifact_hash=repeat('d',64)
    ) or (select count(*) from private.deployment_receipts where action='withdraw_uploaded') <> 1
      or (select count(*) from private.deployment_receipts where action='rollback') <> 2 then
        raise exception 'unrecorded_upload_rollback_not_recorded';
    end if;
    begin
        perform public.record_deployed_release(failed, 'local-smoke-failed-upload', repeat('b',64));
        raise exception 'withdrawn_upload_was_recorded_as_live';
    exception when check_violation then
        if sqlerrm <> 'deployment_record_mismatch' then raise; end if;
    end;
end;
$$;
\echo 'Deployment DB contract passed: uploaded smoke failure, stale-pointer refusal, exact original artifact restoration and append-only withdrawal receipts.'
