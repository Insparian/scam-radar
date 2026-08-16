import { describe, expect, it } from "vitest";

import {
  MAX_QUERY_LENGTH,
  normalizeQuery,
  searchPatterns,
} from "@/lib/public-data/search";
import type { SearchIndexItem } from "@/lib/public-data/types";

const index: SearchIndexItem[] = [
  {
    slug: "million-protection",
    canonical_name: "“百万保障”假客服骗局",
    aliases: ["百万保障扣费", "微信百万保障"],
    keywords: ["屏幕共享", "安全账户"],
  },
  {
    slug: "family-emergency",
    canonical_name: "冒充亲属紧急事故骗局",
    aliases: ["孩子撞人了", "孙子出事"],
    keywords: ["保释金", "上门取现金"],
  },
];

describe("local search", () => {
  it("normalizes punctuation, full-width text and whitespace", () => {
    expect(normalizeQuery(" “百 万 保 障”！ ")).toBe("百万保障");
  });

  it("caps the query before matching", () => {
    expect(normalizeQuery("测".repeat(100))).toHaveLength(MAX_QUERY_LENGTH);
  });

  it("ranks an exact alias ahead of keyword matches", () => {
    const results = searchPatterns("孩子撞人了", index);
    expect(results[0]).toMatchObject({ slug: "family-emergency", score: 95 });
  });

  it("resolves common user wording through a keyword", () => {
    expect(searchPatterns("屏幕共享", index)[0]?.slug).toBe(
      "million-protection",
    );
  });

  it("returns an empty list without transmitting or guessing", () => {
    expect(searchPatterns("完全无关的词", index)).toEqual([]);
  });
});
