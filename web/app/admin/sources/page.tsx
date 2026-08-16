const sourceGroups = [
  { tier: "A1", name: "执法 / 司法机关", count: 8 },
  { tier: "A2", name: "监管 / 公共机构", count: 4 },
  { tier: "B", name: "高可信媒体", count: 3 },
];

export default function SourcesAdminPage() {
  return (
    <main id="main-content" className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">SOURCE REGISTRY · 15 CANDIDATES</span>
          <h1>Sources</h1>
          <p>所有候选来源默认关闭；需要核对入口、政策和 fixture 后才能启用。</p>
        </div>
        <div className="kill-switch">
          <span aria-hidden="true" />
          真实采集关闭
        </div>
      </header>
      <section className="source-group-grid">
        {sourceGroups.map((group) => (
          <article key={group.tier}>
            <span className="source-tier-large">{group.tier}</span>
            <div>
              <strong>{group.name}</strong>
              <p>{group.count} 个候选 · 0 个启用</p>
            </div>
          </article>
        ))}
      </section>
      <section className="activation-lock">
        <strong>Activation lock</strong>
        <p>
          当前没有任何真实网站请求。首批五个来源必须逐一完成政策和 fixture
          复核，并由 Rui 批准后才能启用。
        </p>
      </section>
    </main>
  );
}
