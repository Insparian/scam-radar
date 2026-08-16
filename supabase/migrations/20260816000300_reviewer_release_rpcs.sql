begin;

create or replace function private.append_review_event(
    p_actor_id uuid,
    p_action text,
    p_target_type text,
    p_target_id uuid,
    p_before_state text,
    p_after_state text,
    p_reason text
)
returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
    event_id uuid;
begin
    insert into public.review_events (
        actor_id,
        action,
        target_type,
        target_id,
        before_state,
        after_state,
        reason
    ) values (
        p_actor_id,
        p_action,
        p_target_type,
        p_target_id,
        p_before_state,
        p_after_state,
        p_reason
    )
    returning id into event_id;

    return event_id;
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
        accepted_at = now()
    where pattern_id = p_pattern_id
      and id = any (accepted_ids)
      and acceptance_status = 'proposed';

    update public.pattern_evidence
    set acceptance_status = 'rejected',
        accepted_by = null,
        accepted_at = null
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
    queue_item public.review_items%rowtype;
    pattern public.scam_patterns%rowtype;
    revision public.pattern_revisions%rowtype;
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

    perform private.apply_evidence_decisions(
        pattern.id,
        actor_id,
        p_accepted_evidence_ids,
        p_rejected_evidence_ids
    );

    update public.pattern_revisions
    set revision_status = 'approved',
        approved_by = actor_id,
        approved_at = now()
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
        resolved_at = now()
    where id = queue_item.id;

    event_id := private.append_review_event(
        actor_id,
        case when p_expected_review_type = 'new_pattern' then 'create_pattern' else 'approve_update' end,
        'pattern_revision',
        revision.id,
        jsonb_build_object(
            'review_item_id', queue_item.id,
            'pattern_id', pattern.id,
            'row_version', pattern.row_version,
            'revision_status', revision.revision_status
        )::text,
        jsonb_build_object(
            'review_item_id', queue_item.id,
            'pattern_id', pattern.id,
            'row_version', pattern.row_version + 1,
            'revision_status', 'approved',
            'content_hash', revision.content_hash
        )::text,
        p_decision_note
    );

    insert into public.publication_changes (
        pattern_id,
        action,
        pattern_revision_id,
        requested_by,
        review_event_id,
        reason
    ) values (
        pattern.id,
        'publish',
        revision.id,
        actor_id,
        event_id,
        p_decision_note
    );

    return revision.id;
end;
$$;

create or replace function public.approve_new_pattern(
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
language sql
security definer
set search_path = ''
as $$
    select private.approve_review_item(
        'new_pattern',
        p_review_item_id,
        p_draft_revision_id,
        p_expected_row_version,
        p_expected_candidate_hash,
        p_expected_content_hash,
        p_accepted_evidence_ids,
        p_rejected_evidence_ids,
        p_decision_note
    );
$$;

create or replace function public.approve_pattern_update(
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
language sql
security definer
set search_path = ''
as $$
    select private.approve_review_item(
        'pattern_update',
        p_review_item_id,
        p_draft_revision_id,
        p_expected_row_version,
        p_expected_candidate_hash,
        p_expected_content_hash,
        p_accepted_evidence_ids,
        p_rejected_evidence_ids,
        p_decision_note
    );
$$;

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
        row_version = row_version + 1
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

create or replace function public.merge_pattern_candidate(
    p_review_item_id uuid,
    p_destination_pattern_id uuid,
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
begin
    perform private.assert_enabled_admin(actor_id);

    select * into queue_item
    from public.review_items
    where id = p_review_item_id
    for update;

    if not found
       or queue_item.review_type <> 'merge'
       or queue_item.status not in ('pending', 'in_review')
       or queue_item.candidate_hash is distinct from p_expected_candidate_hash
       or queue_item.target_id = p_destination_pattern_id
       or not exists (select 1 from public.scam_patterns where id = p_destination_pattern_id) then
        raise exception using errcode = '23514', message = 'merge_candidate_changed_or_invalid';
    end if;

    if btrim(coalesce(p_decision_note, '')) = '' then
        raise exception using errcode = '23514', message = 'decision_note_required';
    end if;

    raise exception using
        errcode = '0A000',
        message = 'merge_requires_reviewed_destination_revision',
        hint = 'Create a destination draft that pins evidence and claim mappings, then approve that immutable revision.';
end;
$$;

create or replace function public.archive_pattern(
    p_pattern_id uuid,
    p_expected_row_version bigint,
    p_reason text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    actor_id uuid := auth.uid();
    pattern public.scam_patterns%rowtype;
    event_id uuid;
begin
    perform private.assert_enabled_admin(actor_id);

    if btrim(coalesce(p_reason, '')) = '' then
        raise exception using errcode = '23514', message = 'reason_required';
    end if;

    select * into pattern
    from public.scam_patterns
    where id = p_pattern_id
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'pattern_not_found';
    end if;

    if pattern.row_version <> p_expected_row_version then
        raise exception using errcode = '40001', message = 'stale_row_version';
    end if;

    update public.scam_patterns
    set lifecycle_status = 'archived',
        row_version = row_version + 1
    where id = pattern.id;

    event_id := private.append_review_event(
        actor_id,
        'archive',
        'pattern',
        pattern.id,
        jsonb_build_object('lifecycle_status', pattern.lifecycle_status, 'row_version', pattern.row_version)::text,
        jsonb_build_object('lifecycle_status', 'archived', 'row_version', pattern.row_version + 1)::text,
        p_reason
    );

    if pattern.latest_approved_revision_id is not null then
        insert into public.publication_changes (pattern_id, action, requested_by, review_event_id, reason)
        values (pattern.id, 'unpublish', actor_id, event_id, p_reason);
    end if;

    return event_id;
end;
$$;

create or replace function public.unpublish_pattern(
    p_pattern_id uuid,
    p_expected_row_version bigint,
    p_reason text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    actor_id uuid := auth.uid();
    pattern public.scam_patterns%rowtype;
    event_id uuid;
begin
    perform private.assert_enabled_admin(actor_id);

    if btrim(coalesce(p_reason, '')) = '' then
        raise exception using errcode = '23514', message = 'reason_required';
    end if;

    select * into pattern
    from public.scam_patterns
    where id = p_pattern_id
    for update;

    if not found or pattern.latest_approved_revision_id is null then
        raise exception using errcode = '23514', message = 'approved_pattern_required';
    end if;

    if pattern.row_version <> p_expected_row_version then
        raise exception using errcode = '40001', message = 'stale_row_version';
    end if;

    update public.scam_patterns
    set row_version = row_version + 1
    where id = pattern.id;

    event_id := private.append_review_event(
        actor_id,
        'unpublish',
        'pattern',
        pattern.id,
        jsonb_build_object('row_version', pattern.row_version, 'latest_approved_revision_id', pattern.latest_approved_revision_id)::text,
        jsonb_build_object('row_version', pattern.row_version + 1, 'publication', 'pending_removal')::text,
        p_reason
    );

    insert into public.publication_changes (pattern_id, action, requested_by, review_event_id, reason)
    values (pattern.id, 'unpublish', actor_id, event_id, p_reason);

    return event_id;
end;
$$;

create or replace function public.prepare_public_release(p_expected_previous_release_id uuid default null)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    previous_release_id uuid;
    new_release_id uuid;
    frozen_manifest_hash text;
begin
    perform private.assert_trusted_service();
    perform pg_advisory_xact_lock(hashtextextended('scam-radar-public-release', 0));
    lock table public.publication_changes in share row exclusive mode;

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
              )
              or not exists (
                  select 1 from public.heat_snapshots
                  where pattern_id = latest_change.pattern_id
              )
          )
    ) then
        raise exception using errcode = '23514', message = 'release_change_not_exportable';
    end if;

    insert into public.public_releases (state)
    values ('approved')
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
        heat_snapshot_id
    )
    select
        new_release_id,
        previous_item.pattern_id,
        previous_item.pattern_revision_id,
        previous_item.heat_snapshot_id
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
        heat_snapshot_id
    )
    select
        new_release_id,
        latest_change.pattern_id,
        latest_change.pattern_revision_id,
        heat.id
    from latest_change
    cross join lateral (
        select snapshot.id
        from public.heat_snapshots as snapshot
        where snapshot.pattern_id = latest_change.pattern_id
        order by snapshot.as_of desc, snapshot.calculated_at desc, snapshot.id desc
        limit 1
    ) as heat
    where latest_change.action = 'publish';

    select encode(
        extensions.digest(
            convert_to(
                coalesce(string_agg(
                    item.pattern_id::text || ':' || item.pattern_revision_id::text || ':' || item.heat_snapshot_id::text,
                    '|' order by item.pattern_id
                ), ''),
                'UTF8'
            ),
            'sha256'
        ),
        'hex'
    ) into frozen_manifest_hash
    from public.public_release_items as item
    where item.release_id = new_release_id;

    update public.public_releases
    set manifest_hash = frozen_manifest_hash
    where id = new_release_id;

    update public.publication_changes
    set applied_release_id = new_release_id
    where applied_release_id is null;

    return new_release_id;
end;
$$;

create or replace function public.export_public_release(p_release_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
    release_payload jsonb;
begin
    perform private.assert_trusted_service();

    if not exists (
        select 1
        from public.public_releases
        where id = p_release_id
          and manifest_hash is not null
          and state in ('approved', 'deploying', 'deployed_unrecorded', 'deployed', 'superseded')
    ) then
        raise exception using errcode = '23514', message = 'release_not_exportable';
    end if;

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
    ) into release_payload
    from public.public_releases as release
    where release.id = p_release_id;

    return release_payload;
end;
$$;

create or replace function public.mark_release_deploying(
    p_release_id uuid,
    p_artifact_hash text,
    p_commit_sha text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    perform private.assert_trusted_service();

    if p_artifact_hash !~ '^[0-9a-f]{64}$' or p_commit_sha !~ '^[0-9a-f]{7,64}$' then
        raise exception using errcode = '22023', message = 'invalid_deployment_hash';
    end if;

    if exists (
        select 1
        from public.public_releases as deployed
        join public.public_releases as target on target.id = p_release_id
        where deployed.state = 'deployed'
          and deployed.release_no > target.release_no
    ) then
        raise exception using errcode = '55000', message = 'older_release_cannot_overwrite_newer';
    end if;

    update public.public_releases
    set state = 'deploying',
        artifact_hash = p_artifact_hash,
        commit_sha = p_commit_sha,
        deploy_started_at = now(),
        redacted_error = null
    where id = p_release_id
      and state in ('approved', 'deploy_failed')
      and manifest_hash is not null;

    if not found then
        raise exception using errcode = '23514', message = 'release_not_deployable';
    end if;
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
begin
    perform private.assert_trusted_service();

    if btrim(coalesce(p_deployment_id, '')) = '' then
        raise exception using errcode = '22023', message = 'deployment_id_required';
    end if;

    select * into target
    from public.public_releases
    where id = p_release_id
    for update;

    if not found then
        raise exception using errcode = 'P0002', message = 'release_not_found';
    end if;

    if target.state = 'deployed'
       and target.deployment_id = p_deployment_id
       and target.artifact_hash = p_artifact_hash then
        return;
    end if;

    if target.state not in ('deploying', 'deployed_unrecorded')
       or target.artifact_hash is distinct from p_artifact_hash then
        raise exception using errcode = '23514', message = 'deployment_record_mismatch';
    end if;

    if exists (
        select 1
        from public.public_releases
        where state = 'deployed'
          and release_no > target.release_no
    ) then
        raise exception using errcode = '55000', message = 'older_release_cannot_overwrite_newer';
    end if;

    update public.public_releases
    set state = 'superseded',
        superseded_at = now()
    where id <> target.id
      and state = 'deployed'
      and release_no < target.release_no;

    update public.public_releases
    set state = 'deployed',
        deployment_id = p_deployment_id,
        deployed_at = now(),
        redacted_error = null
    where id = target.id;
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
    set state = 'deploy_failed',
        redacted_error = p_redacted_error
    where id = p_release_id
      and state in ('approved', 'deploying', 'deployed_unrecorded');

    if not found then
        raise exception using errcode = '23514', message = 'release_failure_not_recordable';
    end if;
end;
$$;

revoke execute on function public.approve_new_pattern(uuid, uuid, bigint, text, text, uuid[], uuid[], text) from public, anon;
revoke execute on function public.approve_pattern_update(uuid, uuid, bigint, text, text, uuid[], uuid[], text) from public, anon;
revoke execute on function public.reject_review_item(uuid, text, text) from public, anon;
revoke execute on function public.hold_for_evidence(uuid, text, text) from public, anon;
revoke execute on function public.merge_pattern_candidate(uuid, uuid, text, text) from public, anon;
revoke execute on function public.archive_pattern(uuid, bigint, text) from public, anon;
revoke execute on function public.unpublish_pattern(uuid, bigint, text) from public, anon;

grant execute on function public.approve_new_pattern(uuid, uuid, bigint, text, text, uuid[], uuid[], text) to authenticated;
grant execute on function public.approve_pattern_update(uuid, uuid, bigint, text, text, uuid[], uuid[], text) to authenticated;
grant execute on function public.reject_review_item(uuid, text, text) to authenticated;
grant execute on function public.hold_for_evidence(uuid, text, text) to authenticated;
grant execute on function public.merge_pattern_candidate(uuid, uuid, text, text) to authenticated;
grant execute on function public.archive_pattern(uuid, bigint, text) to authenticated;
grant execute on function public.unpublish_pattern(uuid, bigint, text) to authenticated;

revoke execute on function public.prepare_public_release(uuid) from public, anon, authenticated;
revoke execute on function public.export_public_release(uuid) from public, anon, authenticated;
revoke execute on function public.mark_release_deploying(uuid, text, text) from public, anon, authenticated;
revoke execute on function public.record_deployed_release(uuid, text, text) from public, anon, authenticated;
revoke execute on function public.record_release_failure(uuid, text) from public, anon, authenticated;

grant execute on function public.prepare_public_release(uuid) to service_role;
grant execute on function public.export_public_release(uuid) to service_role;
grant execute on function public.mark_release_deploying(uuid, text, text) to service_role;
grant execute on function public.record_deployed_release(uuid, text, text) to service_role;
grant execute on function public.record_release_failure(uuid, text) to service_role;

commit;
