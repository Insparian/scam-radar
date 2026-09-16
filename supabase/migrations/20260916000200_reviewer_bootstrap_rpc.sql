begin;

create or replace function public.get_reviewer_bootstrap()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
    actor_id uuid := auth.uid();
    actor_role text;
    payload jsonb;
begin
    perform private.assert_enabled_admin(actor_id);

    select role into actor_role
    from public.admin_users
    where user_id = actor_id
      and enabled;

    select jsonb_build_object(
        'reviewer', jsonb_build_object(
            'user_id', actor_id,
            'role', actor_role
        ),
        'queue', coalesce(
            jsonb_agg(
                jsonb_build_object(
                    'id', queue_item.id,
                    'review_type', queue_item.review_type,
                    'status', queue_item.status,
                    'priority', queue_item.priority,
                    'heat_at_creation', queue_item.heat_at_creation,
                    'evidence_level_at_creation', queue_item.evidence_level_at_creation,
                    'reason_codes', queue_item.reason_codes,
                    'candidate_schema_version', queue_item.candidate_schema_version,
                    'candidate_hash', queue_item.candidate_hash,
                    'base_row_version', queue_item.base_row_version,
                    'created_at', queue_item.created_at,
                    'pattern', case
                        when pattern.id is null or revision.id is null then null
                        else jsonb_build_object(
                            'id', pattern.id,
                            'slug', pattern.slug,
                            'lifecycle_status', pattern.lifecycle_status,
                            'row_version', pattern.row_version,
                            'draft_revision', jsonb_build_object(
                                'id', revision.id,
                                'schema_version', revision.schema_version,
                                'content_hash', revision.content_hash,
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
                                'last_material_change_at', revision.last_material_change_at
                            )
                        )
                    end,
                    'policy', case
                        when policy_decision.id is null then null
                        else jsonb_build_object(
                            'id', policy_decision.id,
                            'surface', policy_decision.surface,
                            'policy_version', policy_decision.policy_version,
                            'gate_version', policy_decision.gate_version,
                            'gate_outcome', policy_decision.gate_outcome,
                            'rules_outcome', policy_decision.rules_outcome,
                            'decision_outcome', policy_decision.decision_outcome,
                            'execution_mode', policy_decision.execution_mode,
                            'publication_authorized', policy_decision.publication_authorized,
                            'model_confidence', policy_decision.model_confidence,
                            'model_confidence_downgrade', policy_decision.model_confidence_downgrade,
                            'reason_codes', policy_decision.reason_codes,
                            'evaluated_at', policy_decision.evaluated_at
                        )
                    end,
                    'heat', case
                        when heat.id is null then null
                        else jsonb_build_object(
                            'score', heat.score,
                            'score_version', heat.score_version,
                            'as_of', heat.as_of,
                            'breakdown', heat.breakdown
                        )
                    end,
                    'evidence', coalesce(evidence.items, '[]'::jsonb)
                ) order by queue_item.priority desc, queue_item.created_at, queue_item.id
            ),
            '[]'::jsonb
        )
    ) into payload
    from public.review_items as queue_item
    left join public.scam_patterns as pattern
      on pattern.id = queue_item.target_id
    left join public.pattern_revisions as revision
      on revision.id = pattern.current_draft_revision_id
    left join lateral (
        select decision.*
        from public.policy_decisions as decision
        where decision.review_item_id = queue_item.id
          and decision.surface = 'public_database'
        order by decision.evaluated_at desc, decision.id desc
        limit 1
    ) as policy_decision on true
    left join lateral (
        select snapshot.*
        from public.heat_snapshots as snapshot
        where snapshot.pattern_id = pattern.id
        order by snapshot.as_of desc, snapshot.calculated_at desc, snapshot.id desc
        limit 1
    ) as heat on true
    left join lateral (
        select jsonb_agg(
            jsonb_build_object(
                'id', pattern_evidence.id,
                'evidence_type', pattern_evidence.evidence_type,
                'origin_group_key', pattern_evidence.origin_group_key,
                'evidence_family_id', pattern_evidence.evidence_family_id,
                'claim_summary', pattern_evidence.claim_summary,
                'event_date', pattern_evidence.event_date,
                'region', pattern_evidence.region,
                'is_material_update', pattern_evidence.is_material_update,
                'acceptance_status', pattern_evidence.acceptance_status,
                'last_verified_at', pattern_evidence.last_verified_at,
                'source_status', pattern_evidence.source_status,
                'source', jsonb_build_object(
                    'name', source.name,
                    'authority_tier', source.authority_tier,
                    'title', source_version.title,
                    'url', source_version.url,
                    'published_at', source_version.published_at
                )
            ) order by pattern_evidence.last_verified_at desc nulls last, pattern_evidence.id
        ) as items
        from public.pattern_evidence as pattern_evidence
        join public.source_item_versions as source_version
          on source_version.id = pattern_evidence.source_item_version_id
        join public.source_items as source_item
          on source_item.id = source_version.source_item_id
        join public.sources as source
          on source.id = source_item.source_id
        where pattern_evidence.pattern_id = pattern.id
    ) as evidence on true
    where queue_item.status in ('pending', 'in_review', 'needs_evidence');

    return coalesce(
        payload,
        jsonb_build_object(
            'reviewer', jsonb_build_object('user_id', actor_id, 'role', actor_role),
            'queue', '[]'::jsonb
        )
    );
end;
$$;

revoke execute on function public.get_reviewer_bootstrap() from public, anon, service_role;
grant execute on function public.get_reviewer_bootstrap() to authenticated;

commit;
