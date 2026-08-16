import type { Metadata } from "next";
import { Suspense } from "react";

import { SiteFooter } from "@/components/site-footer";
import { getRelease, getSearchIndex } from "@/lib/public-data/load";

import { SearchClient } from "./search-client";

export const metadata: Metadata = {
  title: "查一查",
  description: "用一个简单关键词，在骗局雷达的已审核模式里查找相似套路。",
  alternates: { canonical: "/search/" },
};

export default function SearchPage() {
  const release = getRelease();
  return (
    <>
      <main id="main-content" className="search-page">
        <div className="shell narrow-shell">
          <div className="search-page-heading">
            <span className="section-kicker">
              LOCAL SEARCH · 关键词只留在你的浏览器
            </span>
            <h1>
              你遇到的事，
              <br />
              像哪一种已知套路？
            </h1>
            <p>输入最明显的一个词就够了，例如“百万保障”“孩子撞人”“粮票”。</p>
          </div>
          <Suspense
            fallback={<div className="search-loading">正在准备本地搜索…</div>}
          >
            <SearchClient
              index={getSearchIndex()}
              patterns={release.patterns}
            />
          </Suspense>
        </div>
      </main>
      <SiteFooter releaseId={release.release_id} />
    </>
  );
}
