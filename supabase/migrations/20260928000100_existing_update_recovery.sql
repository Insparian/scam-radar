begin;

-- Keep the original transactional writer unchanged and private. The public
-- wrapper gives the same receipt shape on first submission and exact replay.
alter function public.submit_existing_pattern_evidence(
    uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[]
) set schema private;
revoke all on function private.submit_existing_pattern_evidence(
    uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[]
) from public, anon, authenticated, service_role;

create function public.submit_existing_pattern_evidence(
    p_version_id uuid,
    p_holder_id text,
    p_run_id uuid,
    p_pattern_id uuid,
    p_base_revision_id uuid,
    p_claim_summary text,
    p_comparison jsonb,
    p_heat jsonb,
    p_candidate_payload jsonb,
    p_reason_codes text[]
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare v_receipt jsonb;
begin
    perform private.assert_trusted_service();
    v_receipt := private.submit_existing_pattern_evidence(
        p_version_id,p_holder_id,p_run_id,p_pattern_id,p_base_revision_id,
        p_claim_summary,p_comparison,p_heat,p_candidate_payload,p_reason_codes
    );
    return v_receipt || jsonb_build_object('missing_claim_count',0);
end;
$$;
revoke all on function public.submit_existing_pattern_evidence(
    uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[]
) from public, anon, authenticated;
grant execute on function public.submit_existing_pattern_evidence(
    uuid,text,uuid,uuid,uuid,text,jsonb,jsonb,jsonb,text[]
) to service_role;

-- A worker may recover only the transaction for the source version it owns
-- *now*. It cannot enumerate other reviews or claim human authority.
create function public.get_existing_update_recovery(
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
    elsif v_review.status <> 'pending'
       or v_pattern.current_draft_revision_id is distinct from v_update.revision_id then
        raise exception using errcode = '23514', message = 'existing_recovery_unreviewed_resolution';
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
        'policy_decision_id',v_policy.id
    );
end;
$$;
revoke all on function public.get_existing_update_recovery(uuid,text)
    from public, anon, authenticated;
grant execute on function public.get_existing_update_recovery(uuid,text)
    to service_role;

commit;
