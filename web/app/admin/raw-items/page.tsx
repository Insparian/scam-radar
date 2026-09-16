import Link from "next/link";

export default function RawItemsAdminPage() {
  return (
    <main id="main-content" className="admin-page admin-empty-state">
      <span className="admin-eyebrow">RAW TEXT NOT EXPOSED TO BROWSER</span>
      <h1>来源条目不在审核浏览器中开放</h1>
      <p>
        Reviewer 只接收最小必要的证据元数据和摘要；raw HTML、clean text 和证据
        spans 不会通过这个 RPC 返回。
      </p>
      <Link className="button-primary" href="/admin/review/">
        返回审核队列
      </Link>
    </main>
  );
}
