import { getRelease } from "@/lib/public-data/load";

export default function RawItemsAdminPage() {
  const release = getRelease();
  return (
    <main id="main-content" className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">NORMALIZED FIXTURE ITEMS</span>
          <h1>Raw Items</h1>
          <p>这里只展示固定测试条目的元数据和哈希提示，不存 raw HTML。</p>
        </div>
      </header>
      <div className="admin-table" role="table" aria-label="固定测试条目">
        <div className="admin-table-row raw header">
          <span>标题</span>
          <span>状态</span>
          <span>内容哈希</span>
          <span>来源</span>
        </div>
        {release.patterns.map((pattern) => (
          <div className="admin-table-row raw" role="row" key={pattern.id}>
            <span>
              <strong>{pattern.canonical_name}</strong>
              <small>fixture://{pattern.slug}</small>
            </span>
            <span>processed</span>
            <code>{pattern.revision_id.replaceAll("-", "").slice(0, 12)}</code>
            <span>fixture-authority</span>
          </div>
        ))}
      </div>
    </main>
  );
}
