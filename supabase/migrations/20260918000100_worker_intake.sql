begin;

-- Narrow worker intake. It cannot mutate evidence, review or release authority.
create or replace function public.ingest_source_version(
    p_source_key text, p_identity_key text, p_url text, p_title text,
    p_clean_text text, p_content_hash text, p_published_at timestamptz,
    p_text_truncated boolean default false
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    source_row public.sources%rowtype;
    item_row public.source_items%rowtype;
    version_id uuid;
    duplicate_id uuid;
begin
    perform private.assert_trusted_service();
    select * into source_row from public.sources where source_key = p_source_key;
    if not found then
        raise exception using errcode = '23514', message = 'source_not_registered';
    end if;
    if not source_row.enabled then
        raise exception using errcode = '23514', message = 'source_not_enabled';
    end if;
    if p_url !~ ('^https://' || replace(source_row.domain, '.', '\.') || '(/|$)')
       or length(p_clean_text) not between 1 and 50000
       or length(p_title) not between 1 and 500
       or p_content_hash !~ '^[0-9a-f]{64}$'
       or p_content_hash <> encode(extensions.digest(btrim(p_title) || E'\n' || btrim(p_clean_text), 'sha256'), 'hex')
       or p_clean_text is null or p_title is null or p_content_hash is null then
        raise exception using errcode = '23514', message = 'invalid_source_payload';
    end if;
    perform pg_advisory_xact_lock(hashtextextended('content:' || p_content_hash, 0));
    -- Serialize a stable identity, including concurrent first inserts.
    perform pg_advisory_xact_lock(hashtextextended(source_row.id::text || ':' || p_identity_key, 0));
    insert into public.source_items(source_id, identity_key, canonical_url, first_seen_at, last_seen_at)
    values(source_row.id, p_identity_key, p_url, now(), now())
    on conflict(source_id, identity_key) do update set last_seen_at = excluded.last_seen_at
    returning * into item_row;
    select id into version_id from public.source_item_versions
    where source_item_id = item_row.id and content_hash = p_content_hash;
    if version_id is not null then return version_id; end if;
    select id into duplicate_id from public.source_item_versions
    where content_hash = p_content_hash order by created_at, id limit 1;
    insert into public.source_item_versions(
        source_item_id, url, canonical_url, title, clean_text, content_hash,
        published_at, fetched_at, text_truncated, origin_group_key,
        duplicate_of_version_id, supersedes_version_id
    ) values (
        item_row.id, p_url, p_url, p_title, p_clean_text, p_content_hash,
        p_published_at, now(), p_text_truncated, p_content_hash,
        duplicate_id, item_row.current_version_id
    ) returning id into version_id;
    update public.source_items set current_version_id = version_id, updated_at = now()
    where id = item_row.id;
    return version_id;
end;
$$;

create or replace function public.store_ai_artifact(
    p_version_id uuid, p_stage text, p_provider text, p_model text,
    p_prompt_version text, p_schema_version text, p_input_hash text,
    p_result jsonb, p_usage jsonb
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    artifact_id uuid;
begin
    perform private.assert_trusted_service();
    if octet_length(p_result::text) > 100000 or octet_length(p_usage::text) > 2000 then
        raise exception using errcode = '23514', message = 'artifact_too_large';
    end if;
    insert into public.ai_artifacts(
        source_item_version_id, stage, provider, model, prompt_version, schema_version,
        input_hash, status, result, usage
    ) values (
        p_version_id, p_stage, p_provider, p_model, p_prompt_version, p_schema_version,
        p_input_hash, 'success', p_result, p_usage
    ) on conflict (source_item_version_id, stage, provider, model, prompt_version, schema_version, input_hash)
    do nothing returning id into artifact_id;
    if artifact_id is null then
        select id into artifact_id from public.ai_artifacts
        where source_item_version_id = p_version_id and stage = p_stage
          and provider = p_provider and model = p_model and prompt_version = p_prompt_version
          and schema_version = p_schema_version and input_hash = p_input_hash and status = 'success'
          and result = p_result;
        if artifact_id is null then
            raise exception using errcode = '23514', message = 'artifact_conflict';
        end if;
    end if;
    return artifact_id;
end;
$$;

create or replace function public.get_ai_artifact(
    p_version_id uuid, p_stage text, p_provider text, p_model text,
    p_prompt_version text, p_schema_version text, p_input_hash text
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
    perform private.assert_trusted_service();
    return (select result from public.ai_artifacts
        where source_item_version_id = p_version_id and stage = p_stage
          and provider = p_provider and model = p_model and prompt_version = p_prompt_version
          and schema_version = p_schema_version and input_hash = p_input_hash and status = 'success');
end;
$$;

revoke all on function public.ingest_source_version(text,text,text,text,text,text,timestamptz,boolean) from public, anon, authenticated;
revoke all on function public.store_ai_artifact(uuid,text,text,text,text,text,text,jsonb,jsonb) from public, anon, authenticated;
revoke all on function public.get_ai_artifact(uuid,text,text,text,text,text,text) from public, anon, authenticated;
grant execute on function public.ingest_source_version(text,text,text,text,text,text,timestamptz,boolean) to service_role;
grant execute on function public.store_ai_artifact(uuid,text,text,text,text,text,text,jsonb,jsonb) to service_role;
grant execute on function public.get_ai_artifact(uuid,text,text,text,text,text,text) to service_role;
commit;
