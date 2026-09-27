begin;

-- Irrelevant source text has no review or publication purpose. Preserve the
-- source identity, hashes and classification artifact for dedupe/audit, but
-- discard the cleaned body once the terminal classification is recorded.
-- The existing content guard stays intact except for this one-way redaction.
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
       or (old.clean_text is distinct from new.clean_text
           and not (new.processing_status = 'irrelevant'
                    and new.clean_text is null
                    and old.processing_status in ('processing', 'irrelevant')))
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

create or replace function private.discard_irrelevant_source_text()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if new.processing_status = 'irrelevant' then
        new.clean_text := null;
    end if;
    return new;
end;
$$;

drop trigger if exists source_item_versions_discard_irrelevant_text on public.source_item_versions;
create trigger source_item_versions_discard_irrelevant_text
before insert or update on public.source_item_versions
for each row execute function private.discard_irrelevant_source_text();

update public.source_item_versions
set clean_text = null
where processing_status = 'irrelevant' and clean_text is not null;

commit;
