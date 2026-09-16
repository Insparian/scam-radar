"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { SupabaseReviewGateway } from "@/lib/review/supabase-gateway";
import type { ReviewerBootstrap } from "@/lib/review/types";

export default function AdminOverview() {
  const [bootstrap, setBootstrap] = useState<ReviewerBootstrap | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const gateway = new SupabaseReviewGateway();
    void gateway
      .loadBootstrap()
      .then(setBootstrap)
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "无法读取审核状态。"),
      );
  }, []);

  const queue = bootstrap?.queue ?? [];
  return (
    <main id="main-content" className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">
            AUTHENTICATED REVIEW · SHADOW POLICY
          </span>
          <h1>发布运营台</h1>
          <p>
            Policy Engine
            先分流，人工只处理例外。审核决定会持久保存，但不会自动部署公开版本。
          </p>
        </div>
        <div className="admin-release">
          <span>Reviewer role</span>
          <code>{bootstrap?.reviewer.role ?? "verifying"}</code>
        </div>
      </header>
      {error && (
        <div className="fixture-message" role="alert">
          {error}
        </div>
      )}
      <section className="admin-stat-grid" aria-label="生产审核状态">
        <article>
          <span>开放审核项</span>
          <strong>{bootstrap ? queue.length : "—"}</strong>
          <small>来自生产数据库的当前例外</small>
        </article>
        <article>
          <span>等待决定</span>
          <strong>
            {bootstrap
              ? queue.filter((item) => item.status === "pending").length
              : "—"}
          </strong>
          <small>尚未由 reviewer 处理</small>
        </article>
        <article>
          <span>等待更多证据</span>
          <strong>
            {bootstrap
              ? queue.filter((item) => item.status === "needs_evidence").length
              : "—"}
          </strong>
          <small>保留但暂不批准</small>
        </article>
        <article>
          <span>自动发布权限</span>
          <strong>0</strong>
          <small>live policy allowlist 仍为空</small>
        </article>
      </section>
      <section className="admin-next">
        <div>
          <span>EXCEPTION PATH</span>
          <h2>处理需要人工判断的候选</h2>
          <p>逐条核对证据、Policy Engine 理由和公开措辞后再作决定。</p>
        </div>
        <Link href="/admin/review/">打开审核队列 →</Link>
      </section>
    </main>
  );
}
