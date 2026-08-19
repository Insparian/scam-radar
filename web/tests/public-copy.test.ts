import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { heatLabel, mechanismHeading } from "@/lib/public-data/copy";
import type { PublicRelease } from "@/lib/public-data/types";

const release = JSON.parse(
  readFileSync(
    path.resolve(
      process.cwd(),
      "../evals/fixtures/public-release/public-release.json",
    ),
    "utf8",
  ),
) as PublicRelease;

describe("public release copy boundaries", () => {
  it("publishes only Evidence A or B", () => {
    expect(
      release.patterns.every((pattern) =>
        ["A", "B"].includes(pattern.evidence_level),
      ),
    ).toBe(true);
  });

  it("keeps risk alerts neutral even with A-level evidence", () => {
    const risk = release.patterns.find(
      (pattern) => pattern.risk_type === "risk_alert",
    );
    expect(risk).toBeDefined();
    expect(mechanismHeading(risk!)).toBe("这种高风险做法通常如何开始");
    expect(risk!.evidence_label).toBe("监管部门已提示风险");
    expect(risk!.mechanism_intro).not.toContain("骗子");
  });

  it("labels inactive content as history rather than current attention", () => {
    expect(heatLabel("observe", false)).toBe("历史记录");
  });

  it("has unique slugs and one exact release ID", () => {
    const slugs = release.patterns.map((pattern) => pattern.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    expect(release.release_id).toBe("fixture-2026-08-16-001");
  });

  it("keeps every pattern traceable and actionable", () => {
    const publishedAt = Date.parse(release.published_at);
    for (const pattern of release.patterns) {
      expect(pattern.warning_signs.length).toBeGreaterThanOrEqual(2);
      expect(pattern.what_to_do.length).toBeGreaterThanOrEqual(2);
      expect(pattern.evidence.length).toBeGreaterThanOrEqual(1);
      expect(pattern.last_verified_at).toMatch(/^2026-/);
      expect(Date.parse(pattern.last_verified_at)).toBe(
        Math.min(
          ...pattern.evidence.map((item) => Date.parse(item.last_verified_at)),
        ),
      );
      expect(Date.parse(pattern.last_verified_at)).toBeLessThanOrEqual(
        publishedAt,
      );
      expect(Date.parse(pattern.verified_at)).toBeLessThanOrEqual(publishedAt);
      expect(
        pattern.evidence.every(
          (item) => Date.parse(item.last_verified_at) <= publishedAt,
        ),
      ).toBe(true);
    }
  });

  it("keeps evidence freshness separate from release publication", () => {
    expect(release.schema_version).toBe(2);
    expect(release.published_at).toMatch(/^2026-/);
    expect(Date.parse(release.generated_at)).toBeLessThanOrEqual(
      Date.parse(release.published_at),
    );
    expect(
      release.patterns.every(
        (pattern) =>
          Date.parse(pattern.last_verified_at) <=
          Date.parse(release.published_at),
      ),
    ).toBe(true);
  });

  it("does not treat evidence and revision verification as the same clock", () => {
    const rechecked = release.patterns.find(
      (pattern) =>
        Date.parse(pattern.last_verified_at) > Date.parse(pattern.verified_at),
    );
    expect(rechecked).toBeDefined();
    expect(Date.parse(rechecked!.last_verified_at)).toBeLessThanOrEqual(
      Date.parse(release.published_at),
    );
  });
});
