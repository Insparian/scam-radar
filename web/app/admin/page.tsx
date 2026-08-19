import Link from "next/link";

import { getRelease } from "@/lib/public-data/load";

export default function AdminOverview() {
  const release = getRelease();
  return (
    <main id="main-content" className="admin-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">POLICY ROUTING · SHADOW MODE</span>
          <h1>发布运营台</h1>
          <p>
            Policy Engine 先按固定规则分流；只有例外进入人工决定。V0.1
            不会自动发布。
          </p>
        </div>
        <div className="admin-release">
          <span>当前固定版本</span>
          <code>{release.release_id}</code>
        </div>
      </header>
      <section className="admin-stat-grid" aria-label="固定测试状态">
        <article>
          <span>规则要求人工决定</span>
          <strong>{release.patterns.length - 1}</strong>
          <small>首次公开或有实质变化</small>
        </article>
        <article>
          <span>影子自动候选</span>
          <strong>1</strong>
          <small>会确认，但不授予自动权限</small>
        </article>
        <article>
          <span>证据 A / B</span>
          <strong>{release.patterns.length}</strong>
          <small>公开候选都先通过 Evidence Gate</small>
        </article>
        <article>
          <span>真实外部写入</span>
          <strong>0</strong>
          <small>activation 前强制为零</small>
        </article>
      </section>
      <section className="admin-next">
        <div>
          <span>EXCEPTION PATH</span>
          <h2>处理例外与影子确认</h2>
          <p>
            同一屏查看 Policy Engine
            理由、证据、Heat、措辞和公开页预览。当前固定模式下的决定不会持久化。
          </p>
        </div>
        <Link href="/admin/review/">打开例外队列 →</Link>
      </section>
    </main>
  );
}
