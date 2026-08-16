"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { heatLabel } from "@/lib/public-data/copy";
import { MAX_QUERY_LENGTH, searchPatterns } from "@/lib/public-data/search";
import type { PublicPattern, SearchIndexItem } from "@/lib/public-data/types";

export function SearchClient({
  index,
  patterns,
}: {
  index: SearchIndexItem[];
  patterns: PublicPattern[];
}) {
  const searchParams = useSearchParams();
  const initial = searchParams.get("q")?.slice(0, MAX_QUERY_LENGTH) ?? "";
  const [input, setInput] = useState(initial);
  const [query, setQuery] = useState(initial);
  const results = useMemo(() => searchPatterns(query, index), [query, index]);
  const bySlug = useMemo(
    () => new Map(patterns.map((pattern) => [pattern.slug, pattern])),
    [patterns],
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(input.trim());
    const url = input.trim()
      ? `/search/?q=${encodeURIComponent(input.trim())}`
      : "/search/";
    window.history.replaceState(null, "", url);
  }

  return (
    <div className="search-workspace">
      <form
        className="search-entry search-entry-page"
        onSubmit={submit}
        role="search"
      >
        <label htmlFor="pattern-query">只输入一个或几个关键词</label>
        <div className="search-control">
          <input
            id="pattern-query"
            value={input}
            maxLength={MAX_QUERY_LENGTH}
            onChange={(event) => setInput(event.target.value)}
            placeholder="例如：百万保障"
            autoFocus
            autoComplete="off"
          />
          <button type="submit">查一查</button>
        </div>
        <p className="input-help">
          不要粘贴姓名、电话、账号、链接或完整聊天记录。
        </p>
      </form>

      {!query && (
        <div className="search-starters">
          <span>可以试试：</span>
          {["百万保障", "孙子出事", "粮票", "免费体检"].map((term) => (
            <button
              key={term}
              onClick={() => {
                setInput(term);
                setQuery(term);
                window.history.replaceState(
                  null,
                  "",
                  `/search/?q=${encodeURIComponent(term)}`,
                );
              }}
            >
              {term}
            </button>
          ))}
        </div>
      )}

      {query && results.length > 0 && (
        <section
          className="search-results"
          aria-live="polite"
          aria-labelledby="results-heading"
        >
          <div className="results-summary">
            <h2 id="results-heading">找到 {results.length} 条相似记录</h2>
            <p>按名称、常见说法和套路关键词匹配</p>
          </div>
          {results.map((result) => {
            const pattern = bySlug.get(result.slug);
            if (!pattern) return null;
            return (
              <article className="search-result" key={result.slug}>
                <div className="result-score">
                  <strong>{result.score}</strong>
                  <span>匹配度</span>
                </div>
                <div className="result-content">
                  <div className="card-meta">
                    <span className="attention-label">
                      <span aria-hidden="true" />
                      {heatLabel(
                        pattern.heat.band,
                        pattern.heat.active_attention,
                      )}
                    </span>
                    <span className="match-reason">{result.matchedBy}</span>
                  </div>
                  <h3>
                    <Link href={`/scam/${pattern.slug}/`}>
                      {pattern.canonical_name}
                    </Link>
                  </h3>
                  <p>{pattern.one_sentence_summary}</p>
                  <div className="do-first">
                    <strong>现在先做：</strong>
                    {pattern.immediate_action}
                  </div>
                </div>
                <Link
                  className="result-link"
                  href={`/scam/${pattern.slug}/`}
                  aria-label={`查看${pattern.canonical_name}`}
                >
                  →
                </Link>
              </article>
            );
          })}
        </section>
      )}

      {query && results.length === 0 && (
        <section className="no-results" aria-live="polite">
          <div className="no-result-mark" aria-hidden="true">
            ?
          </div>
          <h2>暂时没有找到相似的已知骗局</h2>
          <p>
            这不代表它一定安全。先不要付款、不要共享屏幕、不要提供验证码；通过你自己找到的官方号码联系相关机构，并请家人一起核实。
          </p>
          <div className="safe-actions">
            <strong>现在可以做</strong>
            <ol>
              <li>停止继续联系或付款</li>
              <li>把情况告诉一位可信的家人</li>
              <li>从官方应用或官网重新找到联系方式</li>
            </ol>
          </div>
        </section>
      )}
    </div>
  );
}
