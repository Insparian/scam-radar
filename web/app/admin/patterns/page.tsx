import Link from "next/link";

import { formatChineseDate } from "@/lib/public-data/copy";
import { getRelease } from "@/lib/public-data/load";

export default function PatternsAdminPage() {
  const release = getRelease();
  return (
    <main id="main-content" className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">IMMUTABLE FIXTURE REVISIONS</span>
          <h1>Scam Patterns</h1>
          <p>公开内容以固定修订为单位；更正不会覆盖旧修订。</p>
        </div>
      </header>
      <div className="admin-table" role="table" aria-label="骗局模式">
        <div className="admin-table-row header" role="row">
          <span>模式</span>
          <span>类型</span>
          <span>证据</span>
          <span>Heat</span>
          <span>人工审核</span>
        </div>
        {release.patterns.map((pattern) => (
          <Link
            className="admin-table-row"
            role="row"
            href={`/scam/${pattern.slug}/`}
            key={pattern.id}
          >
            <span>
              <strong>{pattern.canonical_name}</strong>
              <small>
                {pattern.revision_id.slice(0, 8)} · {pattern.slug}
              </small>
            </span>
            <span>{pattern.risk_type}</span>
            <span>{pattern.evidence_level}</span>
            <span>{pattern.heat.score}</span>
            <span>{formatChineseDate(pattern.last_reviewed_at)}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
