import Link from "next/link";

import { getRelease } from "@/lib/public-data/load";

export default function AdminOverview() {
  const release = getRelease();
  return (
    <main id="main-content" className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">OFFLINE REVIEW WORKSPACE</span>
          <h1>审核台</h1>
          <p>先验证机器判断，再决定是否形成不可变的公开修订。</p>
        </div>
        <div className="admin-release">
          <span>当前固定版本</span>
          <code>{release.release_id}</code>
        </div>
      </header>
      <section className="admin-stat-grid" aria-label="固定测试状态">
        <article>
          <span>待审核</span>
          <strong>{release.patterns.length}</strong>
          <small>全部来自固定测试资料</small>
        </article>
        <article>
          <span>证据 A</span>
          <strong>
            {
              release.patterns.filter(
                (pattern) => pattern.evidence_level === "A",
              ).length
            }
          </strong>
          <small>权威来源测试记录</small>
        </article>
        <article>
          <span>证据 B</span>
          <strong>
            {
              release.patterns.filter(
                (pattern) => pattern.evidence_level === "B",
              ).length
            }
          </strong>
          <small>独立来源测试记录</small>
        </article>
        <article>
          <span>真实外部写入</span>
          <strong>0</strong>
          <small>activation 前强制为零</small>
        </article>
      </section>
      <section className="admin-next">
        <div>
          <span>建议从这里开始</span>
          <h2>逐条检查 Review Queue</h2>
          <p>
            同一屏查看证据、Heat、措辞和公开页预览。固定模式下的决定不会持久化。
          </p>
        </div>
        <Link href="/admin/review/">打开审核队列 →</Link>
      </section>
    </main>
  );
}
