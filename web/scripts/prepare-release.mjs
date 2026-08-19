import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const webRoot = process.cwd();
const defaultRelease = path.resolve(
  webRoot,
  "../evals/fixtures/public-release/public-release.json",
);
const releasePath = path.resolve(
  webRoot,
  process.env.SCAM_RADAR_RELEASE_PATH ?? defaultRelease,
);
const outputRoot = path.join(webRoot, "public");

const release = JSON.parse(await readFile(releasePath, "utf8"));
if (
  release.schema_version !== 2 ||
  typeof release.release_id !== "string" ||
  typeof release.manifest_hash !== "string" ||
  !/^[a-f0-9]{64}$/.test(release.manifest_hash) ||
  typeof release.generated_at !== "string" ||
  typeof release.published_at !== "string" ||
  !Array.isArray(release.patterns)
) {
  throw new Error("Public release does not match schema version 2");
}
const generatedAt = Date.parse(release.generated_at);
const publishedAt = Date.parse(release.published_at);
if (!Number.isFinite(generatedAt) || !Number.isFinite(publishedAt)) {
  throw new Error("Public release timestamps must be valid ISO dates");
}
if (generatedAt > publishedAt) {
  throw new Error("Public release cannot be published before it is generated");
}
const slugs = release.patterns.map((pattern) => pattern.slug);
if (new Set(slugs).size !== slugs.length) {
  throw new Error("Public release contains duplicate slugs");
}
for (const pattern of release.patterns) {
  if (!Array.isArray(pattern.evidence) || pattern.evidence.length === 0) {
    throw new Error(`Pattern ${pattern.slug} has no supporting evidence`);
  }
  if (
    typeof pattern.verified_at !== "string" ||
    typeof pattern.last_verified_at !== "string" ||
    pattern.evidence.some(
      (evidence) => typeof evidence.last_verified_at !== "string",
    )
  ) {
    throw new Error(
      `Pattern ${pattern.slug} is missing verification timestamps`,
    );
  }
  const revisionVerifiedAt = Date.parse(pattern.verified_at);
  const publicLastVerifiedAt = Date.parse(pattern.last_verified_at);
  const evidenceVerifiedTimes = pattern.evidence.map((evidence) =>
    Date.parse(evidence.last_verified_at),
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
const expectedReleaseId = process.env.NEXT_PUBLIC_RELEASE_ID;
if (expectedReleaseId && expectedReleaseId !== release.release_id) {
  throw new Error(
    `Release mismatch: expected ${expectedReleaseId}, got ${release.release_id}`,
  );
}

const searchIndex = {
  schema_version: 1,
  release_id: release.release_id,
  items: release.patterns.map((pattern) => ({
    slug: pattern.slug,
    canonical_name: pattern.canonical_name,
    aliases: pattern.aliases,
    keywords: pattern.search_terms,
  })),
};
const releaseMetadata = {
  release_id: release.release_id,
  schema_version: release.schema_version,
  manifest_hash: release.manifest_hash,
  pattern_count: release.patterns.length,
  generated_at: release.generated_at,
  published_at: release.published_at,
};

await mkdir(outputRoot, { recursive: true });
await writeFile(
  path.join(outputRoot, "search-index.json"),
  `${JSON.stringify(searchIndex)}\n`,
);
await writeFile(
  path.join(outputRoot, "release.json"),
  `${JSON.stringify(releaseMetadata)}\n`,
);
console.log(
  `prepared immutable release ${release.release_id} (${release.patterns.length} patterns)`,
);
