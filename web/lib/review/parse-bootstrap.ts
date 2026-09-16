import type { Json } from "@/lib/generated/database.types";

import type {
  ReviewerBootstrap,
  ReviewerDraftRevision,
  ReviewerEvidence,
  ReviewerPolicyDecision,
  ReviewerQueueItem,
} from "./types";

type JsonObject = { [key: string]: Json | undefined };

function object(value: Json | undefined, field: string): JsonObject {
  if (!value || Array.isArray(value) || typeof value !== "object") {
    throw new Error(`reviewer_bootstrap_invalid:${field}`);
  }
  return value;
}

function array(value: Json | undefined, field: string): Json[] {
  if (!Array.isArray(value))
    throw new Error(`reviewer_bootstrap_invalid:${field}`);
  return value;
}

function string(value: Json | undefined, field: string): string {
  if (typeof value !== "string")
    throw new Error(`reviewer_bootstrap_invalid:${field}`);
  return value;
}

function nullableString(value: Json | undefined, field: string): string | null {
  if (value === null) return null;
  return string(value, field);
}

function number(value: Json | undefined, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value))
    throw new Error(`reviewer_bootstrap_invalid:${field}`);
  return value;
}

function nullableNumber(value: Json | undefined, field: string): number | null {
  if (value === null) return null;
  return number(value, field);
}

function boolean(value: Json | undefined, field: string): boolean {
  if (typeof value !== "boolean")
    throw new Error(`reviewer_bootstrap_invalid:${field}`);
  return value;
}

function strings(value: Json | undefined, field: string): string[] {
  return array(value, field).map((item, index) =>
    string(item, `${field}.${index}`),
  );
}

function parseRevision(value: Json, field: string): ReviewerDraftRevision {
  const row = object(value, field);
  return {
    id: string(row.id, `${field}.id`),
    schemaVersion: string(row.schema_version, `${field}.schema_version`),
    contentHash: string(row.content_hash, `${field}.content_hash`),
    canonicalName: string(row.canonical_name, `${field}.canonical_name`),
    shortName: nullableString(row.short_name, `${field}.short_name`),
    patternType: string(row.pattern_type, `${field}.pattern_type`),
    riskType: string(row.risk_type, `${field}.risk_type`),
    evidenceLevel: string(row.evidence_level, `${field}.evidence_level`),
    legalStatus: string(row.legal_status, `${field}.legal_status`),
    publicEvidenceLabel: nullableString(
      row.public_evidence_label,
      `${field}.public_evidence_label`,
    ),
    oneSentenceSummary: string(
      row.one_sentence_summary,
      `${field}.one_sentence_summary`,
    ),
    targetPopulation: strings(
      row.target_population,
      `${field}.target_population`,
    ),
    contactChannels: strings(row.contact_channels, `${field}.contact_channels`),
    impersonatedIdentities: strings(
      row.impersonated_identities,
      `${field}.impersonated_identities`,
    ),
    hooks: strings(row.hooks, `${field}.hooks`),
    commonPhrases: strings(row.common_phrases, `${field}.common_phrases`),
    pressureTactics: strings(row.pressure_tactics, `${field}.pressure_tactics`),
    requestedActions: strings(
      row.requested_actions,
      `${field}.requested_actions`,
    ),
    moneyPaths: strings(row.money_paths, `${field}.money_paths`),
    technologyUsed: strings(row.technology_used, `${field}.technology_used`),
    warningSigns: strings(row.warning_signs, `${field}.warning_signs`),
    whatToDo: strings(row.what_to_do, `${field}.what_to_do`),
    regions: strings(row.regions, `${field}.regions`),
    firstSeenAt: string(row.first_seen_at, `${field}.first_seen_at`),
    lastSeenAt: string(row.last_seen_at, `${field}.last_seen_at`),
    lastMaterialChangeAt: nullableString(
      row.last_material_change_at,
      `${field}.last_material_change_at`,
    ),
  };
}

function parsePolicy(value: Json, field: string): ReviewerPolicyDecision {
  const row = object(value, field);
  return {
    id: string(row.id, `${field}.id`),
    surface: string(
      row.surface,
      `${field}.surface`,
    ) as ReviewerPolicyDecision["surface"],
    policyVersion: string(row.policy_version, `${field}.policy_version`),
    gateVersion: string(row.gate_version, `${field}.gate_version`),
    gateOutcome: string(row.gate_outcome, `${field}.gate_outcome`),
    rulesOutcome: string(
      row.rules_outcome,
      `${field}.rules_outcome`,
    ) as ReviewerPolicyDecision["rulesOutcome"],
    decisionOutcome: string(
      row.decision_outcome,
      `${field}.decision_outcome`,
    ) as ReviewerPolicyDecision["decisionOutcome"],
    executionMode: string(
      row.execution_mode,
      `${field}.execution_mode`,
    ) as ReviewerPolicyDecision["executionMode"],
    publicationAuthorized: boolean(
      row.publication_authorized,
      `${field}.publication_authorized`,
    ),
    modelConfidence: nullableNumber(
      row.model_confidence,
      `${field}.model_confidence`,
    ),
    modelConfidenceDowngrade: boolean(
      row.model_confidence_downgrade,
      `${field}.model_confidence_downgrade`,
    ),
    reasonCodes: strings(row.reason_codes, `${field}.reason_codes`),
    evaluatedAt: string(row.evaluated_at, `${field}.evaluated_at`),
  };
}

function parseEvidence(value: Json, field: string): ReviewerEvidence {
  const row = object(value, field);
  const source = object(row.source, `${field}.source`);
  return {
    id: string(row.id, `${field}.id`),
    evidenceType: string(row.evidence_type, `${field}.evidence_type`),
    originGroupKey: string(row.origin_group_key, `${field}.origin_group_key`),
    evidenceFamilyId: nullableString(
      row.evidence_family_id,
      `${field}.evidence_family_id`,
    ),
    claimSummary: string(row.claim_summary, `${field}.claim_summary`),
    eventDate: nullableString(row.event_date, `${field}.event_date`),
    region: nullableString(row.region, `${field}.region`),
    isMaterialUpdate: boolean(
      row.is_material_update,
      `${field}.is_material_update`,
    ),
    acceptanceStatus: string(
      row.acceptance_status,
      `${field}.acceptance_status`,
    ) as ReviewerEvidence["acceptanceStatus"],
    lastVerifiedAt: nullableString(
      row.last_verified_at,
      `${field}.last_verified_at`,
    ),
    sourceStatus: string(row.source_status, `${field}.source_status`),
    source: {
      name: string(source.name, `${field}.source.name`),
      authorityTier: string(
        source.authority_tier,
        `${field}.source.authority_tier`,
      ),
      title: string(source.title, `${field}.source.title`),
      url: string(source.url, `${field}.source.url`),
      publishedAt: nullableString(
        source.published_at,
        `${field}.source.published_at`,
      ),
    },
  };
}

function parseQueueItem(value: Json, field: string): ReviewerQueueItem {
  const row = object(value, field);
  const patternRow =
    row.pattern === null ? null : object(row.pattern, `${field}.pattern`);
  const heatRow = row.heat === null ? null : object(row.heat, `${field}.heat`);
  return {
    id: string(row.id, `${field}.id`),
    reviewType: string(row.review_type, `${field}.review_type`),
    status: string(
      row.status,
      `${field}.status`,
    ) as ReviewerQueueItem["status"],
    priority: number(row.priority, `${field}.priority`),
    heatAtCreation: nullableNumber(
      row.heat_at_creation,
      `${field}.heat_at_creation`,
    ),
    evidenceLevelAtCreation: nullableString(
      row.evidence_level_at_creation,
      `${field}.evidence_level_at_creation`,
    ),
    reasonCodes: strings(row.reason_codes, `${field}.reason_codes`),
    candidateSchemaVersion: string(
      row.candidate_schema_version,
      `${field}.candidate_schema_version`,
    ),
    candidateHash: string(row.candidate_hash, `${field}.candidate_hash`),
    baseRowVersion: number(row.base_row_version, `${field}.base_row_version`),
    createdAt: string(row.created_at, `${field}.created_at`),
    pattern: patternRow
      ? {
          id: string(patternRow.id, `${field}.pattern.id`),
          slug: string(patternRow.slug, `${field}.pattern.slug`),
          lifecycleStatus: string(
            patternRow.lifecycle_status,
            `${field}.pattern.lifecycle_status`,
          ),
          rowVersion: number(
            patternRow.row_version,
            `${field}.pattern.row_version`,
          ),
          draftRevision: parseRevision(
            patternRow.draft_revision as Json,
            `${field}.pattern.draft_revision`,
          ),
        }
      : null,
    policy:
      row.policy === null
        ? null
        : parsePolicy(row.policy as Json, `${field}.policy`),
    heat: heatRow
      ? {
          score: number(heatRow.score, `${field}.heat.score`),
          scoreVersion: string(
            heatRow.score_version,
            `${field}.heat.score_version`,
          ),
          asOf: string(heatRow.as_of, `${field}.heat.as_of`),
          breakdown: heatRow.breakdown ?? null,
        }
      : null,
    evidence: array(row.evidence, `${field}.evidence`).map((item, index) =>
      parseEvidence(item, `${field}.evidence.${index}`),
    ),
  };
}

export function parseReviewerBootstrap(value: Json): ReviewerBootstrap {
  const root = object(value, "root");
  const reviewer = object(root.reviewer, "reviewer");
  const role = string(reviewer.role, "reviewer.role");
  if (role !== "reviewer" && role !== "admin") {
    throw new Error("reviewer_bootstrap_invalid:reviewer.role");
  }
  return {
    reviewer: {
      userId: string(reviewer.user_id, "reviewer.user_id"),
      role,
    },
    queue: array(root.queue, "queue").map((item, index) =>
      parseQueueItem(item, `queue.${index}`),
    ),
  };
}
