import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { SiteFooter } from "@/components/site-footer";
import {
  formatChineseDate,
  heatLabel,
  mechanismHeading,
} from "@/lib/public-data/copy";
import { getPattern, getRelease } from "@/lib/public-data/load";

export const dynamicParams = false;

export function generateStaticParams() {
  return getRelease().patterns.map((pattern) => ({ slug: pattern.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const pattern = getPattern(slug);
  if (!pattern) return { title: "记录未找到" };
  return {
    title: pattern.canonical_name,
    description: pattern.one_sentence_summary,
    alternates: { canonical: `/scam/${pattern.slug}/` },
    openGraph: {
      title: `${pattern.canonical_name}｜骗局雷达`,
      description: pattern.one_sentence_summary,
      type: "article",
    },
  };
}

export default async function PatternPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const release = getRelease();
  const pattern = getPattern(slug);
  if (!pattern) notFound();
  const componentLabels: Record<string, string> = {
    target_relevance: "中老年相关",
    freshness: "最近变化",
    harm: "潜在伤害",
    spread: "影响范围",
    novelty: "套路变化",
  };

  return (
    <>
      <main id="main-content" className="detail-page">
        <div className="shell detail-shell">
          <nav className="breadcrumbs" aria-label="面包屑">
            <Link href="/">首页</Link>
            <span aria-hidden="true">/</span>
            <Link href="/search/">骗局数据库</Link>
            <span aria-hidden="true">/</span>
            <span>{pattern.short_name}</span>
          </nav>

          <header className="detail-hero">
            <div className="detail-status-row">
              <span className={`large-status heat-${pattern.heat.band}`}>
                <span aria-hidden="true" />
                {heatLabel(pattern.heat.band, pattern.heat.active_attention)} ·
                Heat {pattern.heat.score}
              </span>
              <span className="evidence-chip">
                证据 {pattern.evidence_level} · {pattern.evidence_label}
              </span>
              <span className="verified-date">
                信息核实至 {formatChineseDate(pattern.last_verified_at)}
              </span>
            </div>
            <h1>{pattern.canonical_name}</h1>
            {pattern.aliases.length > 0 && (
              <p className="aliases">
                <span>也常被说成</span>
                {pattern.aliases.join("、")}
              </p>
            )}
            <p className="detail-summary">{pattern.one_sentence_summary}</p>
            <section
              className="immediate-panel"
              aria-labelledby="immediate-heading"
            >
              <div className="immediate-number" aria-hidden="true">
                先
              </div>
              <div>
                <h2 id="immediate-heading">现在先做什么</h2>
                <p>{pattern.immediate_action}</p>
              </div>
            </section>
          </header>

          <div className="detail-layout">
            <div className="detail-main">
              <section
                className="detail-section"
                aria-labelledby="starts-heading"
              >
                <span className="detail-index">01</span>
                <h2 id="starts-heading">{mechanismHeading(pattern)}</h2>
                <p className="section-lead">{pattern.mechanism_intro}</p>
              </section>

              <section
                className="detail-section"
                aria-labelledby="next-heading"
              >
                <span className="detail-index">02</span>
                <h2 id="next-heading">接下来通常会发生什么</h2>
                <ol className="mechanism-list">
                  {pattern.mechanism_steps.map((step, index) => (
                    <li key={step}>
                      <span>{index + 1}</span>
                      <p>{step}</p>
                    </li>
                  ))}
                </ol>
              </section>

              <section
                className="detail-section danger-section"
                aria-labelledby="danger-heading"
              >
                <span className="detail-index">03</span>
                <h2 id="danger-heading">最危险的信号</h2>
                <ul className="warning-list">
                  {pattern.warning_signs.map((sign) => (
                    <li key={sign}>
                      <span aria-hidden="true">!</span>
                      {sign}
                    </li>
                  ))}
                </ul>
              </section>

              <section
                className="detail-section"
                aria-labelledby="encounter-heading"
              >
                <span className="detail-index">04</span>
                <h2 id="encounter-heading">如果已经遇到了怎么办</h2>
                <ol className="action-list">
                  {pattern.what_to_do.map((action, index) => (
                    <li key={action}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <p>{action}</p>
                    </li>
                  ))}
                </ol>
              </section>

              <section
                className="detail-section"
                aria-labelledby="timeline-heading"
              >
                <span className="detail-index">05</span>
                <h2 id="timeline-heading">已知案例与变化</h2>
                <div className="timeline">
                  {pattern.timeline.map((item) => (
                    <article key={`${item.date}-${item.title}`}>
                      <time dateTime={item.date}>
                        {formatChineseDate(item.date)}
                      </time>
                      <span aria-hidden="true" />
                      <div>
                        <strong>
                          {item.material ? "重要变化" : "相关记录"}
                        </strong>
                        <p>{item.title}</p>
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <section
                className="detail-section evidence-section"
                aria-labelledby="evidence-heading"
              >
                <span className="detail-index">06</span>
                <h2 id="evidence-heading">证据来源</h2>
                <p className="section-lead">
                  下面是来源事实。上方的步骤和保护建议是骗局雷达基于这些来源整理后的综合说明。
                </p>
                <div className="evidence-list">
                  {pattern.evidence.map((item) => (
                    <article key={item.url}>
                      <div className="source-tier">{item.authority_tier}</div>
                      <div>
                        <div className="source-meta">
                          <strong>{item.institution}</strong>
                          <time dateTime={item.date}>
                            {formatChineseDate(item.date)}
                          </time>
                        </div>
                        <small className="source-verified">
                          来源信息核实至{" "}
                          {formatChineseDate(item.last_verified_at)}
                        </small>
                        <h3>{item.title}</h3>
                        <p>{item.claim_summary}</p>
                        <a href={item.url} target="_blank" rel="noreferrer">
                          查看原始来源 <span aria-hidden="true">↗</span>
                        </a>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            </div>

            <aside className="detail-aside" aria-label="关注度说明">
              <div className="heat-panel">
                <div className="heat-score">
                  <strong>{pattern.heat.score}</strong>
                  <span>/ 100</span>
                </div>
                <h2>为什么现在值得看</h2>
                <p>
                  Heat
                  是关注顺序，不是“为真概率”。事实是否足够公开，由证据等级决定。
                </p>
                <dl>
                  {Object.entries(pattern.heat.components).map(
                    ([key, value]) => (
                      <div key={key}>
                        <dt>{componentLabels[key]}</dt>
                        <dd>
                          <span
                            style={{
                              width: `${(value / ({ target_relevance: 30, freshness: 20, harm: 20, spread: 15, novelty: 15 }[key] ?? 30)) * 100}%`,
                            }}
                          />
                          <b>{value}</b>
                        </dd>
                      </div>
                    ),
                  )}
                </dl>
              </div>
              <div className="aside-note">
                <strong>这条记录的边界</strong>
                <p>
                  {pattern.risk_type === "risk_alert"
                    ? "这是监管提示的高风险做法，不自动等同于刑事诈骗。"
                    : `当前措辞依据“${pattern.evidence_label}”，不扩展到来源没有支持的主体或结论。`}
                </p>
              </div>
              <div className="aside-note">
                <strong>Last Verified / 信息核实至</strong>
                <p>
                  {formatChineseDate(pattern.last_verified_at)}
                  <br />
                  取当前内容所依赖证据的最早核实时间
                </p>
              </div>
              <div className="aside-note">
                <strong>Release / 当前版本形成于</strong>
                <p>
                  {formatChineseDate(release.published_at)}
                  <br />
                  内容版本 {pattern.revision_id.slice(0, 8)}
                </p>
              </div>
            </aside>
          </div>
        </div>
      </main>
      <SiteFooter releaseId={release.release_id} />
    </>
  );
}
