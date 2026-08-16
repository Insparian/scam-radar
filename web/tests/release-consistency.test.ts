import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

function json(relative: string) {
  return JSON.parse(
    readFileSync(path.resolve(process.cwd(), relative), "utf8"),
  );
}

describe("immutable release contract", () => {
  it("keeps fixture pages and local search on the same release", () => {
    const release = json(
      "../evals/fixtures/public-release/public-release.json",
    );
    const search = json("../evals/fixtures/public-release/search-index.json");
    expect(search.release_id).toBe(release.release_id);
    expect(
      search.items.map((item: { slug: string }) => item.slug).sort(),
    ).toEqual(
      release.patterns.map((pattern: { slug: string }) => pattern.slug).sort(),
    );
  });

  it("does not include a backend or model secret shape in public fixtures", () => {
    const body = readFileSync(
      path.resolve(
        process.cwd(),
        "../evals/fixtures/public-release/public-release.json",
      ),
      "utf8",
    );
    expect(body).not.toMatch(
      /SUPABASE_SECRET|SERVICE_ROLE|GEMINI_API_KEY|CLOUDFLARE_API_TOKEN/,
    );
  });
});
