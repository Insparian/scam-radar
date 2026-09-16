import Link from "next/link";

export default function AuthCallbackPage() {
  return (
    <main id="main-content" className="admin-page auth-callback">
      <span className="admin-eyebrow">AUTH METHOD NOT ENABLED</span>
      <h1>这个登录链接方式未启用</h1>
      <p>当前审核台只接受 reviewer 的邮箱和密码登录。</p>
      <Link className="button-primary" href="/admin/login/">
        返回登录页
      </Link>
    </main>
  );
}
