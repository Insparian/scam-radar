"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { MAX_QUERY_LENGTH } from "@/lib/public-data/search";

export function SearchEntry({ compact = false }: { compact?: boolean }) {
  const [query, setQuery] = useState("");
  const router = useRouter();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/search/?q=${encodeURIComponent(value)}` : "/search/");
  }

  return (
    <form
      className={`search-entry ${compact ? "search-entry-compact" : ""}`}
      onSubmit={submit}
      role="search"
    >
      <label htmlFor={compact ? "site-search-compact" : "site-search"}>
        {compact ? "换一个关键词" : "搜索你遇到的可疑事情"}
      </label>
      <div className="search-control">
        <input
          id={compact ? "site-search-compact" : "site-search"}
          name="q"
          maxLength={MAX_QUERY_LENGTH}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="百万保障 / 孙子出事 / 高价回收 / 免费体检…"
          autoComplete="off"
        />
        <button type="submit">查一查</button>
      </div>
      {!compact && (
        <p className="input-help">
          请只输入关键词，不要粘贴姓名、电话、账号或完整聊天记录。
        </p>
      )}
    </form>
  );
}
