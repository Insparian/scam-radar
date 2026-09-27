import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { assertRelease } from "../lib/public-data/validate.ts";

if (
  process.env.SCAM_RADAR_ENV === "production" &&
  (!process.env.SCAM_RADAR_RELEASE_PATH || !process.env.NEXT_PUBLIC_RELEASE_ID)
) {
  throw new Error(
    "Production requires an explicit immutable release path and ID",
  );
}

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
assertRelease(release);
if (
  process.env.SCAM_RADAR_ENV === "production" &&
  release.release_id.startsWith("fixture-")
) {
  throw new Error("Production cannot use a fixture release");
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
