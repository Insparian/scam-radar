import type { PublicRelease } from "./types";

export function assertRelease(value: unknown): asserts value is PublicRelease {
  if (!value || typeof value !== "object")
    throw new Error("Release must be an object");
  const candidate = value as Partial<PublicRelease>;
  if (
    candidate.schema_version !== 2 ||
    typeof candidate.release_id !== "string" ||
    typeof candidate.manifest_hash !== "string" ||
    !/^[a-f0-9]{64}$/.test(candidate.manifest_hash) ||
    typeof candidate.generated_at !== "string" ||
    typeof candidate.published_at !== "string"
  ) {
    throw new Error("Unsupported public release schema");
  }
  if (!Array.isArray(candidate.patterns))
    throw new Error("Release patterns must be an array");
  const generatedAt = Date.parse(candidate.generated_at);
  const publishedAt = Date.parse(candidate.published_at);
  if (!Number.isFinite(generatedAt) || !Number.isFinite(publishedAt)) {
    throw new Error("Release timestamps must be valid ISO dates");
  }
  if (generatedAt > publishedAt) {
    throw new Error("Release cannot be published before it is generated");
  }
  const slugs = candidate.patterns.map((pattern) => pattern.slug);
  if (new Set(slugs).size !== slugs.length)
    throw new Error("Release slugs must be unique");
  if (
    candidate.patterns.some(
      (pattern) => !["A", "B"].includes(pattern.evidence_level),
    )
  ) {
    throw new Error("Static release may contain only Evidence A/B patterns");
  }
  for (const pattern of candidate.patterns) {
    for (const field of [
      "id",
      "revision_id",
      "slug",
      "evidence_label",
      "canonical_name",
      "short_name",
      "one_sentence_summary",
      "immediate_action",
      "mechanism_intro",
      "first_seen_at",
      "last_material_change_at",
    ] as const) {
      if (typeof pattern[field] !== "string" || !pattern[field].trim()) {
        throw new Error(`Missing public field: ${field}`);
      }
    }
    for (const field of [
      "aliases",
      "mechanism_steps",
      "warning_signs",
      "what_to_do",
      "categories",
      "search_terms",
      "regions",
    ] as const) {
      if (
        !Array.isArray(pattern[field]) ||
        pattern[field].some((item) => typeof item !== "string" || !item.trim())
      ) {
        throw new Error(`Invalid public field: ${field}`);
      }
    }
    if (
      !pattern.mechanism_steps.length ||
      !pattern.warning_signs.length ||
      !pattern.what_to_do.length
    ) {
      throw new Error(
        "Public mechanism, warning signs and protective actions are required",
      );
    }
    if (
      !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(pattern.slug) ||
      !["confirmed_scam", "risk_alert"].includes(pattern.risk_type) ||
      ![
        "warning",
        "reported_case",
        "enforcement",
        "charge",
        "judgment",
        "unknown",
      ].includes(pattern.legal_status) ||
      (pattern.risk_type === "risk_alert" &&
        pattern.legal_status !== "warning" &&
        pattern.legal_status !== "enforcement" &&
        pattern.legal_status !== "unknown")
    ) {
      throw new Error("Invalid public identity or risk wording");
    }
    if (
      !pattern.heat ||
      pattern.heat.version !== "scam-heat-v0.1" ||
      !Number.isInteger(pattern.heat.score) ||
      pattern.heat.score < 0 ||
      pattern.heat.score > 100 ||
      typeof pattern.heat.active_attention !== "boolean" ||
      !["immediate", "recent", "observe", "database"].includes(
        pattern.heat.band,
      ) ||
      !Number.isFinite(Date.parse(pattern.heat.as_of))
    ) {
      throw new Error("Invalid public Heat snapshot");
    }
    const maxima = {
      target_relevance: 30,
      freshness: 20,
      harm: 20,
      spread: 15,
      novelty: 15,
    };
    let total = 0;
    for (const [key, max] of Object.entries(maxima)) {
      const points = pattern.heat.components?.[key as keyof typeof maxima];
      if (!Number.isInteger(points) || points < 0 || points > max)
        throw new Error("Invalid Heat component");
      total += points;
    }
    if (total !== pattern.heat.score) throw new Error("Heat total mismatch");
    if (
      !Array.isArray(pattern.timeline) ||
      pattern.timeline.some(
        (item) =>
          !Number.isFinite(Date.parse(item.date)) ||
          typeof item.title !== "string" ||
          !item.title.trim() ||
          typeof item.material !== "boolean",
      )
    ) {
      throw new Error("Invalid public timeline");
    }
    if (
      !Array.isArray(pattern.evidence) ||
      pattern.evidence.some(
        (item) =>
          !["institution", "title", "claim_summary"].every(
            (field) =>
              typeof item[field as keyof typeof item] === "string" &&
              String(item[field as keyof typeof item]).trim(),
          ) ||
          !["A1", "A2", "B"].includes(item.authority_tier) ||
          !Number.isFinite(Date.parse(item.date)) ||
          !/^https:\/\//.test(item.url),
      )
    ) {
      throw new Error("Invalid public evidence");
    }
    if (!pattern.evidence.length) {
      throw new Error("Every public pattern must have supporting evidence");
    }
    if (
      typeof pattern.verified_at !== "string" ||
      typeof pattern.last_verified_at !== "string" ||
      pattern.evidence.some((item) => typeof item.last_verified_at !== "string")
    ) {
      throw new Error(
        `Pattern ${pattern.slug} is missing verification timestamps`,
      );
    }
    const revisionVerifiedAt = Date.parse(pattern.verified_at);
    const publicLastVerifiedAt = Date.parse(pattern.last_verified_at);
    const evidenceVerifiedTimes = pattern.evidence.map((item) =>
      Date.parse(item.last_verified_at),
    );
    if (
      !Number.isFinite(revisionVerifiedAt) ||
      !Number.isFinite(publicLastVerifiedAt) ||
      evidenceVerifiedTimes.some((timestamp) => !Number.isFinite(timestamp))
    ) {
      throw new Error(
        `Pattern ${pattern.slug} has invalid verification timestamps`,
      );
    }
    const conservativeVerifiedAt = Math.min(...evidenceVerifiedTimes);
    if (publicLastVerifiedAt !== conservativeVerifiedAt) {
      throw new Error(
        `Pattern ${pattern.slug} has a non-conservative last_verified_at`,
      );
    }
    if (
      publicLastVerifiedAt > publishedAt ||
      revisionVerifiedAt > publishedAt ||
      evidenceVerifiedTimes.some((timestamp) => timestamp > publishedAt)
    ) {
      throw new Error(
        `Pattern ${pattern.slug} has a verification timestamp after its release`,
      );
    }
  }
}
