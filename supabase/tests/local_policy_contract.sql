\set ON_ERROR_STOP on

begin;

create temporary table local_contract_context (
    policy_decision_id uuid,
    release_id uuid
) on commit drop;

do $$
declare
    applied_versions text[];
begin
    select array_agg(version order by version)
    into applied_versions
    from supabase_migrations.schema_migrations;

    if applied_versions is distinct from array[
        '20260816000100',
        '20260816000200',
        '20260816000300',
        '20260816000400',
        '20260916000100',
        '20260916000200'
    ]::text[] then
        raise exception 'unexpected_migration_set: %', applied_versions;
    end if;

    if has_function_privilege(
        'service_role',
        'public.confirm_policy_publication(uuid,uuid,uuid,bigint,text,text,uuid[],uuid[],text)',
        'EXECUTE'
    ) then
        raise exception 'service_role_can_confirm_human_publication';
    end if;

    if not has_function_privilege(
        'authenticated',
        'public.confirm_policy_publication(uuid,uuid,uuid,bigint,text,text,uuid[],uuid[],text)',
        'EXECUTE'
    ) then
        raise exception 'authenticated_cannot_confirm_human_publication';
    end if;

    if not has_function_privilege(
        'authenticated',
        'public.get_reviewer_bootstrap()',
        'EXECUTE'
    ) or has_function_privilege(
        'anon',
        'public.get_reviewer_bootstrap()',
        'EXECUTE'
    ) or has_function_privilege(
        'service_role',
        'public.get_reviewer_bootstrap()',
        'EXECUTE'
    ) then
        raise exception 'reviewer_bootstrap_rpc_grant_invalid';
    end if;

    if not has_function_privilege(
        'service_role',
        'public.record_policy_decision(uuid,uuid,text,text,text,text,text,text,text,text,text,boolean,boolean,text[],uuid,numeric)',
        'EXECUTE'
    ) or not has_function_privilege(
        'service_role',
        'public.apply_live_policy_publication(uuid,bigint,text,text,uuid[],uuid[])',
        'EXECUTE'
    ) then
        raise exception 'service_role_policy_rpc_grant_missing';
    end if;

    if has_function_privilege(
        'authenticated',
        'public.apply_live_policy_publication(uuid,bigint,text,text,uuid[],uuid[])',
        'EXECUTE'
    ) or has_function_privilege(
        'service_role',
        'public.approve_new_pattern(uuid,uuid,bigint,text,text,uuid[],uuid[],text)',
        'EXECUTE'
    ) or has_function_privilege(
        'authenticated',
        'public.approve_pattern_update(uuid,uuid,bigint,text,text,uuid[],uuid[],text)',
        'EXECUTE'
    ) then
        raise exception 'legacy_or_cross_role_publication_grant_present';
    end if;

    if exists (select 1 from private.active_live_publication_policies()) then
        raise exception 'v0_1_live_policy_allowlist_must_be_empty';
    end if;
end;
$$;

insert into auth.users (
    id,
    aud,
    role,
    email,
    raw_app_meta_data,
    raw_user_meta_data,
    created_at,
    updated_at
) values (
    'eeeeeeee-0000-4000-8000-000000000001',
    'authenticated',
    'authenticated',
    'local-reviewer@scam-radar.invalid',
    '{}'::jsonb,
    '{}'::jsonb,
    now(),
    now()
);

insert into public.admin_users (user_id, role, enabled)
values ('eeeeeeee-0000-4000-8000-000000000001', 'reviewer', true);

insert into public.evidence_claim_support (
    pattern_revision_id,
    field_path,
    value_hash,
    pattern_evidence_id,
    evidence_span_id
)
select
    '60000000-0000-4000-8000-000000000001',
    claim.field_path,
    claim.value_hash,
    '70000000-0000-4000-8000-000000000001',
    '80000000-0000-4000-8000-000000000001'
from private.revision_public_claims(
    '60000000-0000-4000-8000-000000000001'
) as claim
on conflict do nothing;

with calculated_hash as (
    select encode(
        extensions.digest(
            convert_to(
                string_agg(
                    evidence.id::text || ':'
                    || version.content_hash || ':'
                    || evidence.origin_group_key || ':'
                    || evidence.evidence_family_id::text || ':'
                    || evidence.evidence_type,
                    '|' order by evidence.id
                ),
                'UTF8'
            ),
            'sha256'
        ),
        'hex'
    ) as evidence_set_hash
    from public.pattern_evidence as evidence
    join public.source_item_versions as version
      on version.id = evidence.source_item_version_id
    where evidence.pattern_id = '50000000-0000-4000-8000-000000000001'
)
update public.pattern_revisions
set evidence_set_hash = calculated_hash.evidence_set_hash
from calculated_hash
where id = '60000000-0000-4000-8000-000000000001';

do $$
declare
    decision_id uuid;
begin
    perform set_config(
        'request.jwt.claims',
        '{"role":"service_role","sub":"eeeeeeee-0000-4000-8000-000000000001"}',
        true
    );
    perform set_config('request.jwt.claim.role', 'service_role', true);
    perform set_config(
        'request.jwt.claim.sub',
        'eeeeeeee-0000-4000-8000-000000000001',
        true
    );

    decision_id := public.record_policy_decision(
        'a0000000-0000-4000-8000-000000000001',
        '60000000-0000-4000-8000-000000000001',
        'public_database',
        'publication-policy-v0.1',
        repeat('a', 64),
        repeat('b', 64),
        'publication-gate-v0.1',
        'eligible_for_policy',
        'safe_to_automate',
        'safe_to_automate',
        'shadow',
        false,
        false,
        array['shadow_would_publish'],
        'b0000000-0000-4000-8000-000000000001',
        0.99000
    );

    insert into local_contract_context (policy_decision_id)
    values (decision_id);

    if not exists (
        select 1
        from public.policy_decisions
        where id = decision_id
          and execution_mode = 'shadow'
          and decision_outcome = 'safe_to_automate'
          and not publication_authorized
    ) then
        raise exception 'shadow_decision_not_recorded_conservatively';
    end if;
end;
$$;

do $$
begin
    perform public.record_policy_decision(
        'a0000000-0000-4000-8000-000000000001',
        '60000000-0000-4000-8000-000000000001',
        'public_database',
        'publication-policy-v0.1',
        repeat('a', 64),
        repeat('c', 64),
        'publication-gate-v0.1',
        'eligible_for_policy',
        'safe_to_automate',
        'safe_to_automate',
        'shadow',
        true,
        false,
        array['invalid_shadow_authority'],
        'b0000000-0000-4000-8000-000000000001',
        0.99000
    );
    raise exception 'expected_shadow_publication_authority_rejection';
exception
    when others then
        if sqlstate <> '42501' or sqlerrm <> 'policy_live_publication_policy_inactive' then
            raise exception 'wrong_shadow_authority_error [%] %', sqlstate, sqlerrm;
        end if;
end;
$$;

do $$
begin
    perform public.record_policy_decision(
        'a0000000-0000-4000-8000-000000000001',
        '60000000-0000-4000-8000-000000000001',
        'public_database',
        'publication-policy-v0.1',
        repeat('a', 64),
        repeat('d', 64),
        'publication-gate-v0.1',
        'eligible_for_policy',
        'review_required',
        'safe_to_automate',
        'shadow',
        false,
        false,
        array['invalid_confidence_escalation'],
        'b0000000-0000-4000-8000-000000000001',
        0.99000
    );
    raise exception 'expected_model_authority_escalation_rejection';
exception
    when check_violation then
        null;
    when others then
        raise exception 'wrong_model_authority_error [%] %', sqlstate, sqlerrm;
end;
$$;

do $$
declare
    downgraded_decision_id uuid;
begin
    downgraded_decision_id := public.record_policy_decision(
        'a0000000-0000-4000-8000-000000000001',
        '60000000-0000-4000-8000-000000000001',
        'distribution',
        'publication-policy-v0.1',
        repeat('a', 64),
        repeat('e', 64),
        'publication-gate-v0.1',
        'eligible_for_policy',
        'safe_to_automate',
        'review_required',
        'shadow',
        false,
        true,
        array['model_confidence_fail_safe'],
        'b0000000-0000-4000-8000-000000000001',
        0.20000
    );

    if not exists (
        select 1
        from public.policy_decisions
        where id = downgraded_decision_id
          and rules_outcome = 'safe_to_automate'
          and decision_outcome = 'review_required'
          and model_confidence_downgrade
          and not publication_authorized
    ) then
        raise exception 'model_confidence_fail_safe_not_recorded';
    end if;
end;
$$;

do $$
declare
    decision_id uuid;
begin
    select policy_decision_id into decision_id
    from local_contract_context;

    begin
        perform public.apply_live_policy_publication(
            decision_id,
            1,
            repeat('2', 64),
            repeat('f', 64),
            array['70000000-0000-4000-8000-000000000001']::uuid[],
            '{}'::uuid[]
        );
        raise exception 'expected_shadow_apply_rejection';
    exception
        when others then
            if sqlstate <> '40001'
               or sqlerrm <> 'live_policy_decision_stale_inactive_or_unsafe' then
                raise exception 'wrong_shadow_apply_error [%] %', sqlstate, sqlerrm;
            end if;
    end;

    begin
        perform public.confirm_policy_publication(
            decision_id,
            'a0000000-0000-4000-8000-000000000001',
            '60000000-0000-4000-8000-000000000001',
            1,
            repeat('2', 64),
            repeat('f', 64),
            array['70000000-0000-4000-8000-000000000001']::uuid[],
            '{}'::uuid[],
            'invalid service confirmation'
        );
        raise exception 'expected_service_identity_rejection';
    exception
        when others then
            if sqlstate <> '42501'
               or sqlerrm <> 'authenticated_reviewer_role_required' then
                raise exception 'wrong_service_identity_error [%] %', sqlstate, sqlerrm;
            end if;
    end;
end;
$$;

do $$
declare
    decision_id uuid;
    approved_revision_id uuid;
    bootstrap jsonb;
begin
    perform set_config(
        'request.jwt.claims',
        '{"role":"authenticated","sub":"eeeeeeee-0000-4000-8000-000000000001"}',
        true
    );
    perform set_config('request.jwt.claim.role', 'authenticated', true);
    perform set_config(
        'request.jwt.claim.sub',
        'eeeeeeee-0000-4000-8000-000000000001',
        true
    );

    select policy_decision_id into decision_id
    from local_contract_context;

    bootstrap := public.get_reviewer_bootstrap();

    if bootstrap #>> '{reviewer,user_id}'
           <> 'eeeeeeee-0000-4000-8000-000000000001'
       or bootstrap #>> '{reviewer,role}' <> 'reviewer'
       or jsonb_array_length(bootstrap -> 'queue') <> 1
       or bootstrap #>> '{queue,0,id}'
           <> 'a0000000-0000-4000-8000-000000000001'
       or bootstrap #>> '{queue,0,pattern,draft_revision,id}'
           <> '60000000-0000-4000-8000-000000000001'
       or bootstrap #>> '{queue,0,policy,id}' <> decision_id::text
       or bootstrap #>> '{queue,0,evidence,0,id}'
           <> '70000000-0000-4000-8000-000000000001'
       or (bootstrap #> '{queue,0}') ? 'candidate_payload' then
        raise exception 'reviewer_bootstrap_payload_invalid: %', bootstrap;
    end if;

    begin
        perform public.confirm_policy_publication(
            decision_id,
            'a0000000-0000-4000-8000-000000000001',
            '60000000-0000-4000-8000-000000000001',
            2,
            repeat('2', 64),
            repeat('f', 64),
            array['70000000-0000-4000-8000-000000000001']::uuid[],
            '{}'::uuid[],
            'stale local test'
        );
        raise exception 'expected_stale_row_version_rejection';
    exception
        when others then
            if sqlstate <> '40001' or sqlerrm <> 'stale_row_version' then
                raise exception 'wrong_stale_version_error [%] %', sqlstate, sqlerrm;
            end if;
    end;

    approved_revision_id := public.confirm_policy_publication(
        decision_id,
        'a0000000-0000-4000-8000-000000000001',
        '60000000-0000-4000-8000-000000000001',
        1,
        repeat('2', 64),
        repeat('f', 64),
        array['70000000-0000-4000-8000-000000000001']::uuid[],
        '{}'::uuid[],
        'Local transaction proves the human exception path.'
    );

    if approved_revision_id <> '60000000-0000-4000-8000-000000000001' then
        raise exception 'unexpected_approved_revision: %', approved_revision_id;
    end if;

    if not exists (
        select 1
        from public.pattern_revisions
        where id = approved_revision_id
          and revision_status = 'approved'
          and verification_path = 'human'
          and verified_at is not null
          and approved_by = 'eeeeeeee-0000-4000-8000-000000000001'
          and verification_policy_decision_id = decision_id
    ) then
        raise exception 'human_verification_provenance_missing';
    end if;

    if not exists (
        select 1
        from public.publication_changes
        where pattern_revision_id = approved_revision_id
          and request_path = 'human'
          and policy_decision_id = decision_id
          and applied_release_id is null
    ) then
        raise exception 'human_publish_request_missing';
    end if;
end;
$$;

do $$
begin
    begin
        update public.pattern_revisions
        set canonical_name = canonical_name || ' changed'
        where id = '60000000-0000-4000-8000-000000000001';
        raise exception 'expected_approved_revision_immutability_rejection';
    exception
        when others then
            if sqlstate <> '55000' or sqlerrm <> 'approved_revision_is_immutable' then
                raise exception 'wrong_revision_immutability_error [%] %', sqlstate, sqlerrm;
            end if;
    end;
end;
$$;

do $$
declare
    new_release_id uuid;
    evidence_verified_at timestamptz;
begin
    perform set_config(
        'request.jwt.claims',
        '{"role":"service_role","sub":"eeeeeeee-0000-4000-8000-000000000001"}',
        true
    );
    perform set_config('request.jwt.claim.role', 'service_role', true);

    new_release_id := public.prepare_public_release(null);
    update local_contract_context set release_id = new_release_id;

    select last_verified_at into evidence_verified_at
    from public.pattern_evidence
    where id = '70000000-0000-4000-8000-000000000001';

    if not exists (
        select 1
        from public.public_releases
        where id = new_release_id
          and state = 'approved'
          and schema_version = 2
          and published_at is not null
          and manifest_hash is not null
    ) then
        raise exception 'immutable_release_not_prepared';
    end if;

    if not exists (
        select 1
        from public.public_release_items
        where release_id = new_release_id
          and pattern_revision_id = '60000000-0000-4000-8000-000000000001'
          and last_verified_at = evidence_verified_at
    ) then
        raise exception 'public_last_verified_at_not_conservative_evidence_minimum';
    end if;

    if not exists (
        select 1
        from public.public_release_evidence_items
        where release_id = new_release_id
          and pattern_evidence_id = '70000000-0000-4000-8000-000000000001'
          and last_verified_at = evidence_verified_at
    ) then
        raise exception 'release_evidence_snapshot_missing';
    end if;

    begin
        update public.public_releases
        set published_at = published_at + interval '1 second'
        where id = new_release_id;
        raise exception 'expected_release_identity_immutability_rejection';
    exception
        when others then
            if sqlstate <> '55000'
               or sqlerrm <> 'public_release_identity_is_immutable' then
                raise exception 'wrong_release_immutability_error [%] %', sqlstate, sqlerrm;
            end if;
    end;

    begin
        update public.public_release_items
        set last_verified_at = last_verified_at - interval '1 second'
        where release_id = new_release_id;
        raise exception 'expected_release_item_immutability_rejection';
    exception
        when others then
            if sqlstate <> '55000' then
                raise exception 'wrong_release_item_immutability_error [%] %', sqlstate, sqlerrm;
            end if;
    end;
end;
$$;

rollback;

\echo 'Local PostgreSQL policy contract passed.'
