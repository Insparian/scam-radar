import type { SearchIndexItem } from "./types";

export const MAX_QUERY_LENGTH = 40;

export interface SearchResult extends SearchIndexItem {
  score: number;
  matchedBy: string;
}

export function normalizeQuery(value: string): string {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[\s\p{P}\p{S}]+/gu, "")
    .slice(0, MAX_QUERY_LENGTH);
}

export function searchPatterns(
  query: string,
  items: SearchIndexItem[],
): SearchResult[] {
  const normalized = normalizeQuery(query);
  if (!normalized) return [];
  const results: SearchResult[] = [];
  for (const item of items) {
    const canonical = normalizeQuery(item.canonical_name);
    const aliases = item.aliases.map(normalizeQuery);
    const keywords = item.keywords.map(normalizeQuery);
    let score = 0;
    let matchedBy = "";
    if (canonical === normalized) {
      score = 100;
      matchedBy = "名称完全匹配";
    } else if (aliases.includes(normalized)) {
      score = 95;
      matchedBy = "常见说法完全匹配";
    } else if (
      canonical.includes(normalized) ||
      normalized.includes(canonical)
    ) {
      score = 82;
      matchedBy = "名称包含这个关键词";
    } else {
      const alias = aliases.find(
        (value) => value.includes(normalized) || normalized.includes(value),
      );
      if (alias) {
        score = 76;
        matchedBy = "常见说法包含这个关键词";
      } else {
        const keywordHits = keywords.filter(
          (value) => value.includes(normalized) || normalized.includes(value),
        ).length;
        if (keywordHits) {
          score = Math.min(70, 54 + keywordHits * 8);
          matchedBy = "套路关键词匹配";
        }
      }
    }
    if (score > 0) results.push({ ...item, score, matchedBy });
  }
  return results.sort(
    (left, right) =>
      right.score - left.score || left.slug.localeCompare(right.slug),
  );
}
