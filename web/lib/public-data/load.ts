import "server-only";

import { readFileSync } from "node:fs";
import path from "node:path";

import type { PublicPattern, PublicRelease, SearchIndexItem } from "./types";

let cachedRelease: PublicRelease | undefined;

function releasePath(): string {
  const configured = process.env.SCAM_RADAR_RELEASE_PATH;
  if (configured) {
    return path.resolve(process.cwd(), configured);
  }
  return path.resolve(
    process.cwd(),
    "../evals/fixtures/public-release/public-release.json",
  );
}

function assertRelease(value: unknown): asserts value is PublicRelease {
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

export function getRelease(): PublicRelease {
  if (cachedRelease) return cachedRelease;
  const value: unknown = JSON.parse(readFileSync(releasePath(), "utf8"));
  assertRelease(value);
  const expected = process.env.NEXT_PUBLIC_RELEASE_ID;
  if (expected && expected !== value.release_id) {
    throw new Error(`Expected release ${expected}, found ${value.release_id}`);
  }
  cachedRelease = value;
  return value;
}

export function getPattern(slug: string): PublicPattern | undefined {
  return getRelease().patterns.find((pattern) => pattern.slug === slug);
}

export function getSearchIndex(): SearchIndexItem[] {
  return getRelease().patterns.map((pattern) => ({
    slug: pattern.slug,
    canonical_name: pattern.canonical_name,
    aliases: pattern.aliases,
    keywords: pattern.search_terms,
  }));
}
