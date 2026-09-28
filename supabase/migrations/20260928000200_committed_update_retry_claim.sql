begin;

-- The pre-submission retry ceiling must not strand an already committed
-- evidence transaction. A claimed, committed update can always be finalized;
-- all other versions retain the original three-attempt ceiling.
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
      and (
          version.attempt_count < 3
          or exists(select 1 from public.source_version_updates as update_item
                    where update_item.source_item_version_id = version.id)
      )
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
revoke all on function public.claim_source_version(text,text,integer)
    from public, anon, authenticated;
grant execute on function public.claim_source_version(text,text,integer)
    to service_role;

commit;
