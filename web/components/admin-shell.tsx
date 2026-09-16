"use client";

import Link from "next/link";
import { useState } from "react";

import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

export function AdminShell({
  children,
  reviewerEmail,
}: {
  children: React.ReactNode;
  reviewerEmail: string;
}) {
  const [signingOut, setSigningOut] = useState(false);
  return (
    <div className="admin-app">
      <aside className="admin-sidebar">
        <Link className="admin-brand" href="/admin/">
          <span className="radar-mark" aria-hidden="true">
            <span />
          </span>
          <span>
            <strong>骗局雷达</strong>
            <small>运营台 · 生产审核</small>
          </span>
        </Link>
        <nav aria-label="运营台导航">
          <Link href="/admin/">
            <span>01</span>Overview
          </Link>
          <Link href="/admin/review/">
            <span>02</span>Review Queue
          </Link>
        </nav>
        <div className="admin-mode">
          <strong>AUTHENTICATED · SHADOW POLICY</strong>
          <p>审核决定会写入生产数据库；自动候选仍不具备自动发布权限。</p>
        </div>
        <div className="admin-session">
          <span>{reviewerEmail}</span>
          <button
            disabled={signingOut}
            onClick={async () => {
              setSigningOut(true);
              await getSupabaseBrowserClient().auth.signOut();
              window.location.replace("/admin/login/");
            }}
          >
            {signingOut ? "正在退出…" : "安全退出"}
          </button>
        </div>
        <Link className="admin-back" href="/">
          ← 返回公开网站
        </Link>
      </aside>
      <div className="admin-content">{children}</div>
    </div>
  );
}
