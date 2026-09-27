import "server-only";

import { readFileSync } from "node:fs";
import path from "node:path";

import type { PublicPattern, PublicRelease, SearchIndexItem } from "./types";

import { assertRelease } from "./validate";

let cachedRelease: PublicRelease | undefined;

function releasePath(): string {
  const configured = process.env.SCAM_RADAR_RELEASE_PATH;
  if (configured) {
    return path.resolve(process.cwd(), configured);
  }
  if (process.env.SCAM_RADAR_ENV === "production") {
    throw new Error("Production requires an explicit immutable release path");
  }
  return path.resolve(
    process.cwd(),
    "../evals/fixtures/public-release/public-release.json",
  );
}

export function getRelease(): PublicRelease {
  if (cachedRelease) return cachedRelease;
  const value: unknown = JSON.parse(readFileSync(releasePath(), "utf8"));
  assertRelease(value);
  const expected = process.env.NEXT_PUBLIC_RELEASE_ID;
  if (
    process.env.SCAM_RADAR_ENV === "production" &&
    (!expected || value.release_id.startsWith("fixture-"))
  ) {
    throw new Error("Production requires an explicit non-fixture release ID");
  }
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
