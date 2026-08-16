"use client";

import Link from "next/link";

export default function AuthCallbackPage() {
  return (
    <main id="main-content" className="admin-page auth-callback">
      <span className="admin-eyebrow">PKCE CALLBACK RESERVED</span>
      <h1>真实审核登录尚未激活</h1>
      <p>
        这个静态路径为 Supabase magic-link PKCE 回调保留。离线阶段不会读取 URL
        token、发起网络请求或创建会话。
      </p>
      <Link className="button-primary" href="/admin/review/">
        返回固定审核演示
      </Link>
    </main>
  );
}
