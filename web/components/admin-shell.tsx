import Link from "next/link";

export function AdminShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="admin-app">
      <aside className="admin-sidebar">
        <Link className="admin-brand" href="/admin/">
          <span className="radar-mark" aria-hidden="true">
            <span />
          </span>
          <span>
            <strong>骗局雷达</strong>
            <small>运营台 · 影子模式</small>
          </span>
        </Link>
        <nav aria-label="运营台导航">
          <Link href="/admin/review/">
            <span>01</span>Review Queue
          </Link>
          <Link href="/admin/patterns/">
            <span>02</span>Scam Patterns
          </Link>
          <Link href="/admin/sources/">
            <span>03</span>Sources
          </Link>
          <Link href="/admin/raw-items/">
            <span>04</span>Raw Items
          </Link>
        </nav>
        <div className="admin-mode">
          <strong>SHADOW · FIXTURE ONLY</strong>
          <p>自动候选只记录影子结果；所有操作都不会写数据库或改变公开版本。</p>
        </div>
        <Link className="admin-back" href="/">
          ← 返回公开网站
        </Link>
      </aside>
      <div className="admin-content">{children}</div>
    </div>
  );
}
