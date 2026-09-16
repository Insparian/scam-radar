import Link from "next/link";

export default function SourcesAdminPage() {
  return (
    <main id="main-content" className="admin-page admin-empty-state">
      <span className="admin-eyebrow">SOURCE ACTIVATION LOCKED</span>
      <h1>真实来源仍未启用</h1>
      <p>
        Source Registry 继续以仓库配置为准。当前浏览器没有来源管理
        RPC，也不会向真实网站发请求。
      </p>
      <Link className="button-primary" href="/admin/review/">
        返回审核队列
      </Link>
    </main>
  );
}
