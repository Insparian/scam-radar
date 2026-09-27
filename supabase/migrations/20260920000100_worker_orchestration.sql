begin;

-- The reviewed registry remains the source of truth. A source cannot be made
-- collectible merely by toggling enabled in an ad-hoc SQL session.
alter table public.sources
    add column collection_allowed boolean not null default false,
    add column reviewed_at date,
    add constraint sources_enable_requires_review check (
        not enabled
        or (collection_allowed and reviewed_at is not null and authority_tier <> 'C')
    );

alter table public.source_item_versions
    add column claim_holder text,
    add column claimed_until timestamptz,
    add constraint source_version_claim_shape check (
        (processing_status = 'processing' and claim_holder is not null and claimed_until is not null)
        or (processing_status <> 'processing' and claim_holder is null and claimed_until is null)
    );

create or replace function public.sync_registry_source(
    p_source_key text,
    p_name text,
    p_domain text,
    p_publisher_group text,
    p_source_type text,
    p_authority_tier text,
    p_ingestion_method text,
    p_entry_url text,
    p_enabled boolean,
    p_collection_allowed boolean,
    p_reviewed_at date,
    p_poll_frequency text,
    p_parser_config jsonb,
    p_config_hash text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_source_id uuid;
    existing_source public.sources%rowtype;
begin
    perform private.assert_trusted_service();
    if p_config_hash !~ '^[0-9a-f]{64}$'
       or p_source_key !~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'
       or p_entry_url !~ '^https://'
       or split_part(split_part(p_entry_url, '/', 3), ':', 1) <> p_domain
       or p_parser_config is null
       or jsonb_typeof(p_parser_config) <> 'object'
       or (p_enabled and (not p_collection_allowed or p_reviewed_at is null
           or p_reviewed_at > current_date or p_authority_tier = 'C'))
    then
        raise exception using errcode = '23514', message = 'source_review_or_config_invalid';
    end if;
    select * into existing_source from public.sources
    where source_key = p_source_key for update;
    if found and (
        existing_source.name is distinct from p_name
        or existing_source.domain is distinct from p_domain
        or existing_source.publisher_group is distinct from p_publisher_group
        or existing_source.source_type is distinct from p_source_type
        or existing_source.authority_tier is distinct from p_authority_tier
        or existing_source.ingestion_method is distinct from p_ingestion_method
    ) then
        raise exception using errcode = '23514', message = 'source_identity_changed';
    end if;
    insert into public.sources (
        source_key, name, domain, publisher_group, source_type,
        authority_tier, ingestion_method, entry_url, enabled,
        collection_allowed, reviewed_at, poll_frequency, parser_config,
        config_hash
    ) values (
        p_source_key, p_name, p_domain, p_publisher_group, p_source_type,
        p_authority_tier, p_ingestion_method, p_entry_url, p_enabled,
        p_collection_allowed, p_reviewed_at, p_poll_frequency, p_parser_config,
        p_config_hash
    )
    on conflict (source_key) do update set
        entry_url = excluded.entry_url,
        enabled = excluded.enabled,
        collection_allowed = excluded.collection_allowed,
        reviewed_at = excluded.reviewed_at,
        poll_frequency = excluded.poll_frequency,
        parser_config = excluded.parser_config,
        config_hash = excluded.config_hash,
        synced_at = now()
    returning id into v_source_id;
    insert into public.source_states(source_id) values(v_source_id)
    on conflict (source_id) do nothing;
    return v_source_id;
end;
$$;

create or replace function public.start_pipeline_run(
    p_trigger text,
    p_commit_sha text,
    p_registry_hash text,
    p_behavior_hash text,
    p_pipeline_version text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare run_id uuid;
begin
    perform private.assert_trusted_service();
    insert into public.pipeline_runs(
        trigger, commit_sha, registry_hash, behavior_hash, pipeline_version
    ) values (
        p_trigger, p_commit_sha, p_registry_hash, p_behavior_hash, p_pipeline_version
    ) returning id into run_id;
    return run_id;
end;
$$;

create or replace function public.finish_pipeline_run(
    p_run_id uuid,
    p_outcome text,
    p_discovered_count integer,
    p_relevant_count integer,
    p_review_count integer,
    p_error_code text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare existing public.pipeline_runs%rowtype;
begin
    perform private.assert_trusted_service();
    if p_outcome not in ('success', 'degraded', 'failed', 'cancelled')
       or p_error_code is not null and p_error_code !~ '^[a-z][a-z0-9_]{0,79}$'
    then
        raise exception using errcode = '23514', message = 'invalid_run_outcome';
    end if;
    select * into existing from public.pipeline_runs where id = p_run_id for update;
    if not found then
        raise exception using errcode = 'P0002', message = 'pipeline_run_not_found';
    end if;
    if existing.outcome <> 'running' then
        if existing.outcome = p_outcome
           and existing.discovered_count = p_discovered_count
           and existing.relevant_count = p_relevant_count
           and existing.review_count = p_review_count
           and existing.error_summary is not distinct from p_error_code
        then return; end if;
        raise exception using errcode = '23514', message = 'pipeline_run_replay_mismatch';
    end if;
    update public.pipeline_runs set
        outcome = p_outcome,
        discovered_count = p_discovered_count,
        relevant_count = p_relevant_count,
        review_count = p_review_count,
        error_summary = p_error_code,
        finished_at = now()
    where id = p_run_id;
end;
$$;

create or replace function public.acquire_operation_lease(
    p_lease_key text, p_holder_id text, p_ttl_seconds integer
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare acquired boolean;
begin
    perform private.assert_trusted_service();
    if p_lease_key !~ '^[a-z0-9:_-]{1,120}$'
       or p_holder_id !~ '^[a-zA-Z0-9:_-]{1,120}$'
       or p_ttl_seconds not between 30 and 900
    then
        raise exception using errcode = '23514', message = 'invalid_lease_request';
    end if;
    insert into public.operation_leases(lease_key, holder_id, acquired_at, expires_at)
    values(p_lease_key, p_holder_id, now(), now() + make_interval(secs => p_ttl_seconds))
    on conflict (lease_key) do update set
        holder_id = excluded.holder_id,
        acquired_at = excluded.acquired_at,
        expires_at = excluded.expires_at
    where public.operation_leases.expires_at <= now()
       or public.operation_leases.holder_id = p_holder_id
    returning true into acquired;
    return coalesce(acquired, false);
end;
$$;

create or replace function public.release_operation_lease(
    p_lease_key text, p_holder_id text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare released boolean;
begin
    perform private.assert_trusted_service();
    delete from public.operation_leases
    where lease_key = p_lease_key and holder_id = p_holder_id
    returning true into released;
    return coalesce(released, false);
end;
$$;

create or replace function public.claim_source_version(
    p_source_key text, p_holder_id text, p_lease_seconds integer default 300
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare claimed public.source_item_versions%rowtype;
begin
    perform private.assert_trusted_service();
    if p_holder_id !~ '^[a-zA-Z0-9:_-]{1,120}$'
       or p_lease_seconds not between 30 and 900
    then
        raise exception using errcode = '23514', message = 'invalid_claim_request';
    end if;
    select version.* into claimed
    from public.source_item_versions as version
    join public.source_items as item on item.id = version.source_item_id
    join public.sources as source on source.id = item.source_id
    where source.source_key = p_source_key
      and source.enabled and source.collection_allowed and source.reviewed_at is not null
      and version.attempt_count < 3
      and (
          version.processing_status in ('pending_ai', 'error')
          or (version.processing_status = 'processing' and version.claimed_until <= now())
      )
    order by version.created_at, version.id
    for update of version skip locked
    limit 1;
    if not found then return null; end if;
    update public.source_item_versions set
        processing_status = 'processing',
        claim_holder = p_holder_id,
        claimed_until = now() + make_interval(secs => p_lease_seconds),
        attempt_count = attempt_count + 1,
        last_error = null
    where id = claimed.id;
    return jsonb_build_object(
        'version_id', claimed.id,
        'url', claimed.canonical_url,
        'title', claimed.title,
        'clean_text', claimed.clean_text,
        'content_hash', claimed.content_hash,
        'published_at', claimed.published_at,
        'fetched_at', claimed.fetched_at,
        'source_key', p_source_key
    );
end;
$$;

create or replace function public.finish_source_version(
    p_version_id uuid, p_holder_id text, p_status text, p_error_code text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare existing public.source_item_versions%rowtype;
begin
    perform private.assert_trusted_service();
    if p_status not in ('processed', 'irrelevant', 'blocked', 'error')
       or (p_status = 'error') is distinct from (p_error_code is not null)
       or p_error_code is not null and p_error_code !~ '^[a-z][a-z0-9_]{0,79}$'
    then
        raise exception using errcode = '23514', message = 'invalid_version_outcome';
    end if;
    select * into existing from public.source_item_versions where id = p_version_id for update;
    if not found then
        raise exception using errcode = 'P0002', message = 'source_version_not_found';
    end if;
    if existing.processing_status <> 'processing'
       or existing.claim_holder <> p_holder_id
    then
        raise exception using errcode = '42501', message = 'source_claim_not_owned';
    end if;
    update public.source_item_versions set
        processing_status = p_status,
        claim_holder = null,
        claimed_until = null,
        last_error = p_error_code
    where id = p_version_id;
end;
$$;

create or replace function public.record_source_checkpoint(
    p_source_key text,
    p_run_id uuid,
    p_success boolean,
    p_cursor_value text default null,
    p_etag text default null,
    p_last_modified text default null,
    p_error_code text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare v_source_id uuid;
begin
    perform private.assert_trusted_service();
    select id into v_source_id from public.sources where source_key = p_source_key;
    if v_source_id is null or not exists(
        select 1 from public.pipeline_runs where id = p_run_id and outcome = 'running'
    ) then
        raise exception using errcode = 'P0002', message = 'checkpoint_target_not_found';
    end if;
    if (p_success and p_error_code is not null)
       or (not p_success and (p_error_code is null or p_error_code !~ '^[a-z][a-z0-9_]{0,79}$'))
       or length(coalesce(p_cursor_value, '')) > 500
       or length(coalesce(p_etag, '')) > 500
       or length(coalesce(p_last_modified, '')) > 500
    then
        raise exception using errcode = '23514', message = 'invalid_source_checkpoint';
    end if;
    insert into public.source_states(source_id, last_attempt_at)
    values(v_source_id, now()) on conflict (source_id) do nothing;
    update public.source_states set
        cursor_value = case when p_success then p_cursor_value else cursor_value end,
        etag = case when p_success then p_etag else etag end,
        last_modified = case when p_success then p_last_modified else last_modified end,
        last_attempt_at = now(),
        last_success_at = case when p_success then now() else last_success_at end,
        consecutive_failures = case when p_success then 0 else consecutive_failures + 1 end,
        last_error_code = p_error_code,
        updated_at = now()
    where public.source_states.source_id = v_source_id;
end;
$$;

revoke all on function public.sync_registry_source(text,text,text,text,text,text,text,text,boolean,boolean,date,text,jsonb,text) from public, anon, authenticated;
revoke all on function public.start_pipeline_run(text,text,text,text,text) from public, anon, authenticated;
revoke all on function public.finish_pipeline_run(uuid,text,integer,integer,integer,text) from public, anon, authenticated;
revoke all on function public.acquire_operation_lease(text,text,integer) from public, anon, authenticated;
revoke all on function public.release_operation_lease(text,text) from public, anon, authenticated;
revoke all on function public.claim_source_version(text,text,integer) from public, anon, authenticated;
revoke all on function public.finish_source_version(uuid,text,text,text) from public, anon, authenticated;
revoke all on function public.record_source_checkpoint(text,uuid,boolean,text,text,text,text) from public, anon, authenticated;
grant execute on function public.sync_registry_source(text,text,text,text,text,text,text,text,boolean,boolean,date,text,jsonb,text) to service_role;
grant execute on function public.start_pipeline_run(text,text,text,text,text) to service_role;
grant execute on function public.finish_pipeline_run(uuid,text,integer,integer,integer,text) to service_role;
grant execute on function public.acquire_operation_lease(text,text,integer) to service_role;
grant execute on function public.release_operation_lease(text,text) to service_role;
grant execute on function public.claim_source_version(text,text,integer) to service_role;
grant execute on function public.finish_source_version(uuid,text,text,text) to service_role;
grant execute on function public.record_source_checkpoint(text,uuid,boolean,text,text,text,text) to service_role;

commit;
