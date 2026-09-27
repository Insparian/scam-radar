import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { assertRelease } from "../lib/public-data/validate";

const fixture = () =>
  JSON.parse(
    readFileSync(
      "../evals/fixtures/public-release/public-release.json",
      "utf8",
    ),
  );

describe("public presentation boundary", () => {
  it("accepts a complete immutable presentation", () =>
    expect(() => assertRelease(fixture())).not.toThrow());
  it.each([
    "immediate_action",
    "mechanism_intro",
    "mechanism_steps",
    "what_to_do",
    "search_terms",
    "heat",
    "timeline",
  ])("rejects missing %s", (field) => {
    const release = fixture();
    delete release.patterns[0][field];
    expect(() => assertRelease(release)).toThrow();
  });
  it("rejects unsafe source links", () => {
    const release = fixture();
    release.patterns[0].evidence[0].url = "javascript:alert(1)";
    expect(() => assertRelease(release)).toThrow();
  });
  it("rejects Heat point inflation", () => {
    const release = fixture();
    release.patterns[0].heat.score += 1;
    expect(() => assertRelease(release)).toThrow("Heat total mismatch");
  });
});
