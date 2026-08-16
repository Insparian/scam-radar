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
    candidate.schema_version !== 1 ||
    typeof candidate.release_id !== "string"
  ) {
    throw new Error("Unsupported public release schema");
  }
  if (!Array.isArray(candidate.patterns))
    throw new Error("Release patterns must be an array");
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
