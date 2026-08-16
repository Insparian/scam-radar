begin;

create or replace function private.assert_enabled_admin(p_actor uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
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

create or replace function private.assert_trusted_service()
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
    if jwt_role is distinct from 'service_role' then
        raise exception using errcode = '42501', message = 'trusted_service_role_required';
    end if;
end;
$$;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

create trigger admin_users_set_updated_at
before update on public.admin_users
for each row execute function private.set_updated_at();

create trigger source_items_set_updated_at
before update on public.source_items
for each row execute function private.set_updated_at();

create trigger scam_patterns_set_updated_at
before update on public.scam_patterns
for each row execute function private.set_updated_at();

create trigger review_items_set_updated_at
before update on public.review_items
for each row execute function private.set_updated_at();

create trigger source_states_set_updated_at
before update on public.source_states
for each row execute function private.set_updated_at();

create or replace function private.protect_review_resolution()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if tg_op = 'INSERT' then
        if new.status <> 'pending' then
            raise exception using errcode = '23514', message = 'review_item_must_start_pending';
        end if;
        return new;
    end if;

    if old.status is distinct from new.status
       and new.status in ('in_review', 'needs_evidence', 'approved', 'rejected', 'merged') then
        perform private.assert_enabled_admin(new.assigned_to);
    end if;

    return new;
end;
$$;

create trigger review_items_protect_resolution
before insert or update on public.review_items
for each row execute function private.protect_review_resolution();

create or replace function private.protect_source_identity()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if old.id is distinct from new.id
       or old.source_key is distinct from new.source_key
       or old.name is distinct from new.name
       or old.domain is distinct from new.domain
       or old.publisher_group is distinct from new.publisher_group
       or old.source_type is distinct from new.source_type
       or old.authority_tier is distinct from new.authority_tier
       or old.created_at is distinct from new.created_at then
        raise exception using errcode = '55000', message = 'source_identity_is_immutable';
    end if;
    return new;
end;
$$;

create trigger sources_protect_identity
before update on public.sources
for each row execute function private.protect_source_identity();

create or replace function private.protect_pattern_identity()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if old.id is distinct from new.id
       or old.slug is distinct from new.slug
       or old.created_at is distinct from new.created_at then
        raise exception using errcode = '55000', message = 'pattern_identity_is_immutable';
    end if;
    return new;
end;
$$;

create trigger scam_patterns_protect_identity
before update on public.scam_patterns
for each row execute function private.protect_pattern_identity();

create or replace function private.protect_source_item_version()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if tg_op = 'DELETE' then
        raise exception using errcode = '55000', message = 'source_item_versions_are_immutable';
    end if;

    if old.id is distinct from new.id
       or old.source_item_id is distinct from new.source_item_id
       or old.url is distinct from new.url
       or old.canonical_url is distinct from new.canonical_url
       or old.title is distinct from new.title
       or old.author is distinct from new.author
       or old.language is distinct from new.language
       or old.published_at is distinct from new.published_at
       or old.fetched_at is distinct from new.fetched_at
       or old.clean_text is distinct from new.clean_text
       or old.text_truncated is distinct from new.text_truncated
       or old.content_hash is distinct from new.content_hash
       or old.raw_html_hash is distinct from new.raw_html_hash
       or old.origin_group_key is distinct from new.origin_group_key
       or old.duplicate_of_version_id is distinct from new.duplicate_of_version_id
       or old.supersedes_version_id is distinct from new.supersedes_version_id
       or old.created_at is distinct from new.created_at then
        raise exception using errcode = '55000', message = 'source_item_version_content_is_immutable';
    end if;

    return new;
end;
$$;

create trigger source_item_versions_protect_content
before update or delete on public.source_item_versions
for each row execute function private.protect_source_item_version();

create or replace function private.prevent_row_change()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    raise exception using errcode = '55000', message = tg_table_name || '_is_append_only';
end;
$$;

create trigger evidence_spans_append_only
before update or delete on public.evidence_spans
for each row execute function private.prevent_row_change();

create trigger review_events_append_only
before update or delete on public.review_events
for each row execute function private.prevent_row_change();

create or replace function private.validate_review_event_actor()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    perform private.assert_enabled_admin(new.actor_id);
    return new;
end;
$$;

create trigger review_events_require_human_actor
before insert on public.review_events
for each row execute function private.validate_review_event_actor();

create trigger heat_snapshots_append_only
before update or delete on public.heat_snapshots
for each row execute function private.prevent_row_change();

create trigger public_release_items_append_only
before update or delete on public.public_release_items
for each row execute function private.prevent_row_change();

create or replace function private.revision_public_claims(p_revision_id uuid)
returns table (field_path text, value_hash text)
language sql
security invoker
set search_path = ''
as $$
    with revision as (
        select *
        from public.pattern_revisions
        where id = p_revision_id
    ), scalar_claims(field_path, claim_value) as (
        select 'canonical_name', canonical_name from revision
        union all select 'short_name', short_name from revision where short_name is not null
        union all select 'pattern_type', pattern_type from revision
        union all select 'risk_type', risk_type from revision
        union all select 'legal_status', legal_status from revision
        union all select 'public_evidence_label', public_evidence_label from revision where public_evidence_label is not null
        union all select 'one_sentence_summary', one_sentence_summary from revision
        union all select 'first_seen_at', to_char(first_seen_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') from revision
        union all select 'last_seen_at', to_char(last_seen_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') from revision
        union all select 'last_material_change_at', to_char(last_material_change_at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
            from revision where last_material_change_at is not null
    ), array_claims(field_path, claim_value) as (
        select 'target_population[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(target_population) with ordinality as item(value, ordinality)
        union all
        select 'contact_channels[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(contact_channels) with ordinality as item(value, ordinality)
        union all
        select 'impersonated_identities[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(impersonated_identities) with ordinality as item(value, ordinality)
        union all
        select 'hooks[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(hooks) with ordinality as item(value, ordinality)
        union all
        select 'common_phrases[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(common_phrases) with ordinality as item(value, ordinality)
        union all
        select 'pressure_tactics[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(pressure_tactics) with ordinality as item(value, ordinality)
        union all
        select 'requested_actions[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(requested_actions) with ordinality as item(value, ordinality)
        union all
        select 'money_paths[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(money_paths) with ordinality as item(value, ordinality)
        union all
        select 'technology_used[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(technology_used) with ordinality as item(value, ordinality)
        union all
        select 'warning_signs[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(warning_signs) with ordinality as item(value, ordinality)
        union all
        select 'what_to_do[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(what_to_do) with ordinality as item(value, ordinality)
        union all
        select 'regions[' || item.ordinality || ']', item.value
        from revision cross join lateral unnest(regions) with ordinality as item(value, ordinality)
        union all
        select 'aliases[' || alias_item.ordinality || ']', alias_item.alias
        from (
            select alias, row_number() over (order by normalized_alias, id) as ordinality
            from public.scam_aliases
            where pattern_revision_id = p_revision_id
        ) as alias_item
    ), claims as (
        select * from scalar_claims
        union all
        select * from array_claims
    )
    select
        claims.field_path,
        encode(extensions.digest(convert_to(claims.claim_value, 'UTF8'), 'sha256'), 'hex')
    from claims;
$$;

create or replace function private.assert_publishable_revision(p_revision_id uuid)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    revision public.pattern_revisions%rowtype;
    accepted_count integer;
    official_count integer;
    family_count integer;
    origin_count integer;
    publisher_count integer;
    region_count integer;
    police_count integer;
    court_count integer;
    regulator_count integer;
    calculated_evidence_set_hash text;
begin
    select * into revision
    from public.pattern_revisions
    where id = p_revision_id;

    if not found then
        raise exception using errcode = '23503', message = 'revision_not_found';
    end if;

    if revision.evidence_level not in ('A', 'B') then
        raise exception using errcode = '23514', message = 'insufficient_evidence';
    end if;

    if revision.public_evidence_label is null
       or cardinality(revision.contact_channels) = 0
       or cardinality(revision.warning_signs) = 0
       or cardinality(revision.what_to_do) = 0
       or (
           cardinality(revision.hooks)
           + cardinality(revision.pressure_tactics)
           + cardinality(revision.requested_actions)
           + cardinality(revision.money_paths)
       ) = 0 then
        raise exception using errcode = '23514', message = 'minimum_public_fields_missing';
    end if;

    select
        count(*) filter (where evidence.source_status = 'available' and source.authority_tier in ('A1', 'A2', 'B')),
        count(*) filter (
            where evidence.source_status = 'available'
              and source.source_type in ('police', 'regulator', 'court')
              and source.authority_tier in ('A1', 'A2')
        ),
        count(distinct evidence.evidence_family_id) filter (
            where evidence.source_status = 'available' and source.authority_tier in ('A1', 'A2', 'B')
        ),
        count(distinct evidence.origin_group_key) filter (
            where evidence.source_status = 'available' and source.authority_tier in ('A1', 'A2', 'B')
        ),
        count(distinct source.publisher_group) filter (
            where evidence.source_status = 'available' and source.authority_tier in ('A1', 'A2', 'B')
        ),
        count(distinct evidence.region) filter (
            where evidence.source_status = 'available'
              and source.authority_tier in ('A1', 'A2', 'B')
              and evidence.region is not null
        ),
        count(*) filter (
            where evidence.source_status = 'available'
              and source.source_type = 'police'
              and source.authority_tier = 'A1'
        ),
        count(*) filter (
            where evidence.source_status = 'available'
              and source.source_type = 'court'
              and source.authority_tier = 'A1'
        ),
        count(*) filter (
            where evidence.source_status = 'available'
              and source.source_type = 'regulator'
              and source.authority_tier in ('A1', 'A2')
        )
    into
        accepted_count,
        official_count,
        family_count,
        origin_count,
        publisher_count,
        region_count,
        police_count,
        court_count,
        regulator_count
    from public.pattern_evidence as evidence
    join public.source_item_versions as version on version.id = evidence.source_item_version_id
    join public.source_items as item on item.id = version.source_item_id
    join public.sources as source on source.id = item.source_id
    where evidence.pattern_id = revision.pattern_id
      and evidence.acceptance_status = 'accepted';

    if accepted_count = 0 then
        raise exception using errcode = '23514', message = 'insufficient_evidence';
    end if;

    if revision.evidence_level = 'A' and official_count = 0 then
        raise exception using errcode = '23514', message = 'authoritative_evidence_required';
    end if;

    if revision.evidence_level = 'B'
       and (family_count < 2 or origin_count < 2 or publisher_count < 2) then
        raise exception using errcode = '23514', message = 'sources_not_independent';
    end if;

    if revision.public_evidence_label = '警方通报的诈骗案件'
       and (police_count = 0 or revision.risk_type <> 'confirmed_scam'
            or revision.legal_status not in ('reported_case', 'enforcement', 'charge')) then
        raise exception using errcode = '23514', message = 'risk_legal_label_incompatible';
    end if;

    if revision.public_evidence_label = '司法机关已公开裁判'
       and (court_count = 0 or revision.risk_type <> 'confirmed_scam' or revision.legal_status <> 'judgment') then
        raise exception using errcode = '23514', message = 'risk_legal_label_incompatible';
    end if;

    if revision.public_evidence_label = '监管部门已提示风险'
       and (regulator_count = 0 or revision.legal_status not in ('warning', 'enforcement')) then
        raise exception using errcode = '23514', message = 'risk_legal_label_incompatible';
    end if;

    if revision.public_evidence_label = '近期多地出现类似套路' and region_count < 2 then
        raise exception using errcode = '23514', message = 'distinct_regions_required';
    end if;

    select encode(
        extensions.digest(
            convert_to(
                coalesce(string_agg(
                    evidence.id::text || ':'
                    || version.content_hash || ':'
                    || evidence.origin_group_key || ':'
                    || evidence.evidence_family_id::text || ':'
                    || evidence.evidence_type,
                    '|' order by evidence.id
                ), ''),
                'UTF8'
            ),
            'sha256'
        ),
        'hex'
    ) into calculated_evidence_set_hash
    from public.pattern_evidence as evidence
    join public.source_item_versions as version on version.id = evidence.source_item_version_id
    where evidence.pattern_id = revision.pattern_id
      and evidence.acceptance_status = 'accepted';

    if revision.evidence_set_hash is distinct from calculated_evidence_set_hash then
        raise exception using errcode = '40001', message = 'evidence_set_changed';
    end if;

    if exists (
        select 1
        from private.revision_public_claims(p_revision_id) as claim
        where not exists (
            select 1
            from public.evidence_claim_support as support
            join public.pattern_evidence as evidence
              on evidence.id = support.pattern_evidence_id
            join public.evidence_spans as span
              on span.id = support.evidence_span_id
             and span.pattern_evidence_id = support.pattern_evidence_id
            where support.pattern_revision_id = p_revision_id
              and support.field_path = claim.field_path
              and support.value_hash = claim.value_hash
              and evidence.pattern_id = revision.pattern_id
              and evidence.acceptance_status = 'accepted'
              and evidence.source_status = 'available'
        )
    ) then
        raise exception using errcode = '23514', message = 'claim_not_supported';
    end if;
end;
$$;

create or replace function private.protect_pattern_revision()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if tg_op = 'INSERT' then
        if new.revision_status = 'approved' then
            perform private.assert_enabled_admin(new.approved_by);
            perform private.assert_publishable_revision(new.id);
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
        perform private.assert_enabled_admin(new.approved_by);
        perform private.assert_publishable_revision(new.id);
    end if;

    return new;
end;
$$;

create trigger pattern_revisions_protect_approval
before insert or update or delete on public.pattern_revisions
for each row execute function private.protect_pattern_revision();

create or replace function private.protect_approved_revision_child()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
    revision_id uuid;
begin
    if tg_table_name = 'scam_aliases' then
        revision_id := case when tg_op = 'DELETE' then old.pattern_revision_id else new.pattern_revision_id end;
    else
        revision_id := case when tg_op = 'DELETE' then old.pattern_revision_id else new.pattern_revision_id end;
    end if;

    if exists (
        select 1 from public.pattern_revisions
        where id = revision_id and revision_status = 'approved'
    ) then
        raise exception using errcode = '55000', message = 'approved_revision_children_are_immutable';
    end if;

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end;
$$;

create trigger scam_aliases_protect_approved_revision
before insert or update or delete on public.scam_aliases
for each row execute function private.protect_approved_revision_child();

create trigger evidence_claim_support_protect_approved_revision
before insert or update or delete on public.evidence_claim_support
for each row execute function private.protect_approved_revision_child();

create or replace function private.protect_resolved_evidence()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if tg_op = 'INSERT' then
        if new.acceptance_status <> 'proposed' then
            raise exception using errcode = '23514', message = 'evidence_must_start_proposed';
        end if;
        return new;
    end if;

    if tg_op = 'DELETE' then
        raise exception using errcode = '55000', message = 'pattern_evidence_is_retained';
    end if;

    if old.acceptance_status = 'proposed' and new.acceptance_status in ('accepted', 'rejected') then
        perform private.assert_enabled_admin(
            case when new.acceptance_status = 'accepted' then new.accepted_by else auth.uid() end
        );
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
        or old.created_at is distinct from new.created_at
    ) then
        raise exception using errcode = '55000', message = 'resolved_evidence_is_immutable';
    end if;

    return new;
end;
$$;

create trigger pattern_evidence_protect_resolution
before insert or update or delete on public.pattern_evidence
for each row execute function private.protect_resolved_evidence();

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
    ) then
        raise exception using errcode = '23514', message = 'release_requires_approved_revision';
    end if;

    if not exists (
        select 1
        from public.heat_snapshots
        where id = new.heat_snapshot_id
          and pattern_id = new.pattern_id
    ) then
        raise exception using errcode = '23514', message = 'release_heat_pattern_mismatch';
    end if;

    return new;
end;
$$;

create trigger public_release_items_validate_insert
before insert on public.public_release_items
for each row execute function private.validate_release_item();

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
       or old.prepared_at is distinct from new.prepared_at
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

create trigger public_releases_protect_history
before update or delete on public.public_releases
for each row execute function private.protect_public_release();

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
       or old.reason is distinct from new.reason
       or old.created_at is distinct from new.created_at
       or old.applied_release_id is not null
       or new.applied_release_id is null then
        raise exception using errcode = '55000', message = 'publication_change_is_immutable';
    end if;

    return new;
end;
$$;

create trigger publication_changes_protect_history
before update or delete on public.publication_changes
for each row execute function private.protect_publication_change();

create or replace function private.validate_publication_change_request()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
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
          and approved_by = new.requested_by
    ) then
        raise exception using errcode = '23514', message = 'publication_requires_human_approved_revision';
    end if;

    if new.action = 'unpublish' and not exists (
        select 1
        from public.scam_patterns
        where id = new.pattern_id
          and latest_approved_revision_id is not null
    ) then
        raise exception using errcode = '23514', message = 'unpublish_requires_approved_pattern';
    end if;

    return new;
end;
$$;

create trigger publication_changes_require_human_request
before insert on public.publication_changes
for each row execute function private.validate_publication_change_request();

alter table public.admin_users enable row level security;
alter table public.sources enable row level security;
alter table public.source_items enable row level security;
alter table public.source_item_versions enable row level security;
alter table public.ai_artifacts enable row level security;
alter table public.scam_patterns enable row level security;
alter table public.pattern_revisions enable row level security;
alter table public.scam_aliases enable row level security;
alter table public.pattern_evidence enable row level security;
alter table public.evidence_spans enable row level security;
alter table public.evidence_claim_support enable row level security;
alter table public.review_items enable row level security;
alter table public.pipeline_runs enable row level security;
alter table public.source_states enable row level security;
alter table public.source_run_results enable row level security;
alter table public.review_events enable row level security;
alter table public.heat_snapshots enable row level security;
alter table public.public_releases enable row level security;
alter table public.public_release_items enable row level security;
alter table public.publication_changes enable row level security;
alter table public.operation_leases enable row level security;

revoke all on all tables in schema public from public, anon, authenticated;
revoke all on all sequences in schema public from public, anon, authenticated;
revoke execute on all functions in schema public from public, anon, authenticated;
revoke create on schema public from public, anon, authenticated;
revoke all on schema private from public, anon, authenticated;
revoke execute on all functions in schema private from public, anon, authenticated;

alter default privileges in schema public revoke all on tables from public, anon, authenticated;
alter default privileges in schema public revoke all on sequences from public, anon, authenticated;
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;
alter default privileges in schema private revoke execute on functions from public, anon, authenticated;

grant usage on schema public to anon, authenticated, service_role;

commit;
