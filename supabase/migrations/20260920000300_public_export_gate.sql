begin;

-- Approval must not create a publication change that the public exporter cannot
-- render without inventing fields. This runs inside the human/policy transaction.
create or replace function private.assert_release_exportable(p_revision_id uuid)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
    revision public.pattern_revisions%rowtype;
    heat public.heat_snapshots%rowtype;
    points integer;
    component text;
    total integer := 0;
begin
    select * into revision from public.pattern_revisions where id = p_revision_id;
    if not found or revision.revision_status <> 'approved'
       or btrim(coalesce(revision.short_name,'')) = ''
       or revision.last_material_change_at is null
       or cardinality(revision.hooks) = 0
       or cardinality(revision.requested_actions) = 0
       or cardinality(revision.warning_signs) = 0
       or cardinality(revision.what_to_do) = 0
       or revision.risk_type = 'risk_alert'
          and revision.legal_status not in ('warning','enforcement','unknown')
    then
        raise exception using errcode = '23514', message = 'public_export_fields_incomplete';
    end if;
    select * into heat from public.heat_snapshots
    where pattern_id = revision.pattern_id
    order by as_of desc, calculated_at desc, id desc limit 1;
    if not found or heat.score_version <> 'scam-heat-v0.1'
       or heat.as_of < revision.last_material_change_at::date
       or heat.breakdown->>'total' is null
       or (heat.breakdown->>'total')::integer <> heat.score then
        raise exception using errcode = '23514', message = 'public_export_heat_invalid';
    end if;
    foreach component in array array[
        'target_relevance','freshness','harm','spread','novelty'
    ] loop
        if jsonb_typeof(heat.breakdown->component) <> 'object'
           or heat.breakdown->component->>'points' is null then
            raise exception using errcode = '23514', message = 'public_export_heat_invalid';
        end if;
        points := (heat.breakdown->component->>'points')::integer;
        if points < 0 or points > (case component
            when 'target_relevance' then 30
            when 'freshness' then 20
            when 'harm' then 20
            when 'spread' then 15
            else 15 end) then
            raise exception using errcode = '23514', message = 'public_export_heat_invalid';
        end if;
        total := total + points;
    end loop;
    if total <> heat.score then
        raise exception using errcode = '23514', message = 'public_export_heat_invalid';
    end if;
end;
$$;

create or replace function private.enforce_publication_exportability()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if new.action = 'publish' then
        perform private.assert_release_exportable(new.pattern_revision_id);
    end if;
    return new;
end;
$$;

create trigger publication_changes_require_exportable_revision
before insert on public.publication_changes
for each row execute function private.enforce_publication_exportability();

revoke all on function private.assert_release_exportable(uuid) from public, anon, authenticated;
revoke all on function private.enforce_publication_exportability() from public, anon, authenticated;
commit;
