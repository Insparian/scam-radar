"use client";

import { useState } from "react";

import {
  getSupabaseBrowserClient,
  getSupabasePublicConfig,
} from "@/lib/supabase/browser";

export default function AdminLoginPage() {
  const configured = Boolean(getSupabasePublicConfig());
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setSubmitting(true);

    const { error } = await getSupabaseBrowserClient().auth.signInWithPassword({
      email: email.trim(),
      password,
    });

    if (error) {
      setMessage(
        error.message.toLowerCase().includes("invalid login")
          ? "邮箱或密码不正确。"
          : "暂时无法登录，请稍后再试。",
      );
      setSubmitting(false);
      return;
    }
    window.location.replace("/admin/review/");
  }

  return (
    <main id="main-content" className="admin-login-page">
      <section className="admin-login-card">
        <span className="admin-eyebrow">PRIVATE REVIEWER ACCESS</span>
        <h1>登录审核台</h1>
        <p>这里只供已启用的 Scam Radar reviewer 使用。</p>

        {!configured ? (
          <div className="admin-login-message" role="status">
            当前构建没有连接生产审核系统，因此不会发送登录信息。
          </div>
        ) : (
          <form onSubmit={submit}>
            <label>
              审核邮箱
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              密码
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {message && (
              <div className="admin-login-message error" role="alert">
                {message}
              </div>
            )}
            <button type="submit" disabled={submitting}>
              {submitting ? "正在验证…" : "登录"}
            </button>
          </form>
        )}
        <small>
          登录凭据和会话信息会发送到已批准的 Frankfurt Supabase
          项目。公开搜索词不会发送。
        </small>
      </section>
    </main>
  );
}
