import Link from "next/link";

import { PatternCard } from "@/components/pattern-card";
import { SearchEntry } from "@/components/search-entry";
import { SiteFooter } from "@/components/site-footer";
import { categoryLabel, formatChineseDate } from "@/lib/public-data/copy";
import { getRelease } from "@/lib/public-data/load";

const categories = [
  "phone",
  "wechat",
  "investment",
  "pension",
  "health_products",
  "family_impersonation",
  "customer_service",
  "collectibles",
];

export default function HomePage() {
  const release = getRelease();
  const today = release.patterns
    .filter(
      (pattern) => pattern.heat.active_attention && pattern.heat.score >= 65,
    )
    .sort((left, right) => right.heat.score - left.heat.score)
    .slice(0, 3);
  const recentChanges = [...release.patterns]
    .sort((left, right) =>
      right.last_material_change_at.localeCompare(left.last_material_change_at),
    )
    .slice(0, 5);

  return (
    <>
      <main id="main-content">
        <section className="hero">
          <div className="shell hero-grid">
            <div className="hero-copy">
              <div className="eyebrow">
                <span aria-hidden="true" /> 给家人的风险备忘录
              </div>
              <h1>
                最近有什么骗局
                <br />
                值得提醒爸妈？
              </h1>
              <p>
                先看懂对方在做什么，再决定下一步。每条记录都经过证据门槛和人工审核。
              </p>
            </div>
            <div className="hero-search-card">
              <SearchEntry />
              <div className="calm-note">
                <strong>记住：</strong>
                正规机构不会要求你共享屏幕、提供验证码或把钱转到“安全账户”。
              </div>
            </div>
          </div>
          <div className="shell trust-strip" aria-label="骗局雷达的三个原则">
            <span>
              <b>01</b> 只看经过选择的可信来源
            </span>
            <span>
              <b>02</b> AI 提议，证据和人做决定
            </span>
            <span>
              <b>03</b> 没查到，不代表一定安全
            </span>
          </div>
        </section>

        {today.length > 0 && (
          <section className="section shell" aria-labelledby="today-heading">
            <div className="section-heading">
              <div>
                <span className="section-kicker">TODAY · 最多 3 条</span>
                <h2 id="today-heading">今天值得注意</h2>
              </div>
              <p>
                这里不是热搜榜，而是近期变化、潜在伤害和中老年相关性综合后的关注顺序。
              </p>
            </div>
            <div className="pattern-grid">
              {today.map((pattern) => (
                <PatternCard key={pattern.id} pattern={pattern} />
              ))}
            </div>
          </section>
        )}

        <section
          className="section section-soft"
          aria-labelledby="changes-heading"
        >
          <div className="shell">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">CHANGES · 有什么新变化</span>
                <h2 id="changes-heading">最近出现变化</h2>
              </div>
              <Link className="text-link" href="/search/">
                查看全部记录 <span aria-hidden="true">→</span>
              </Link>
            </div>
            <div className="change-list">
              {recentChanges.map((pattern, index) => (
                <Link
                  className="change-row"
                  href={`/scam/${pattern.slug}/`}
                  key={pattern.id}
                >
                  <span className="change-index">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="change-main">
                    <strong>{pattern.canonical_name}</strong>
                    <span>
                      {pattern.timeline[0]?.title ??
                        pattern.one_sentence_summary}
                    </span>
                  </span>
                  <time dateTime={pattern.last_material_change_at}>
                    {formatChineseDate(pattern.last_material_change_at)}
                  </time>
                  <span className="change-arrow" aria-hidden="true">
                    →
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </section>

        <section className="section shell" aria-labelledby="categories-heading">
          <div className="section-heading compact-heading">
            <div>
              <span className="section-kicker">
                COMMON PATTERNS · 从熟悉的词开始
              </span>
              <h2 id="categories-heading">常见骗局</h2>
            </div>
          </div>
          <div className="category-grid">
            {categories.map((category, index) => (
              <Link
                href={`/search/?q=${encodeURIComponent(categoryLabel(category))}`}
                key={category}
              >
                <span className="category-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <strong>{categoryLabel(category)}</strong>
                <span aria-hidden="true">↗</span>
              </Link>
            ))}
          </div>
        </section>

        <section
          className="section methodology"
          id="methodology"
          aria-labelledby="method-heading"
        >
          <div className="shell methodology-grid">
            <div className="method-intro">
              <span className="section-kicker">HOW WE DECIDE · 判断方法</span>
              <h2 id="method-heading">
                “值得关注”
                <br />
                不等于“已经证实”
              </h2>
              <p>
                骗局雷达把两件事分开：证据决定能说到什么程度，Heat
                只决定现在是否值得优先看。
              </p>
            </div>
            <div className="method-cards">
              <article>
                <span className="method-letter">E</span>
                <div>
                  <h3>Evidence Gate · 证据门槛</h3>
                  <p>
                    A 表示有权威来源；B 表示有多个独立可信来源。C/D
                    只留在内部，不会包装成公开骗局。
                  </p>
                </div>
              </article>
              <article>
                <span className="method-letter">H</span>
                <div>
                  <h3>Scam Heat · 关注优先级</h3>
                  <p>
                    由代码按目标人群、最近变化、伤害、传播和新颖程度计算。Heat
                    高不代表事实更真。
                  </p>
                </div>
              </article>
              <article>
                <span className="method-letter">人</span>
                <div>
                  <h3>Human Review · 人工审核</h3>
                  <p>
                    只有审核员确认证据、措辞和保护建议后，才会进入下一次不可变的公开版本。
                  </p>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section
          className="section shell trust-sections"
          aria-label="来源、隐私和运营说明"
        >
          <article id="sources">
            <span>01</span>
            <h2>来源范围</h2>
            <p>
              V0.1
              只覆盖中国大陆，并只计划采集公安、司法、监管部门和可追溯的高可信媒体。当前页面使用固定测试资料，尚未连接真实来源。
            </p>
          </article>
          <article id="privacy">
            <span>02</span>
            <h2>搜索隐私</h2>
            <p>
              搜索在你的浏览器里对当前版本的本地索引进行匹配。骗局雷达不上传、不保存你的关键词，也不接受完整聊天记录或个人资料。
            </p>
          </article>
          <article id="corrections">
            <span>03</span>
            <h2>更正与下架</h2>
            <p>
              每条内容都有人工审核时间和证据链接。当前是离线演示；正式上线前会公布更正和紧急下架联系方式。
            </p>
          </article>
          <article id="about">
            <span>04</span>
            <h2>关于我们</h2>
            <p>
              骗局雷达由 Insparian
              运营，目标是把公开风险信息变成家人真正能用的记忆，而不是制造恐慌或追逐流量。
            </p>
          </article>
        </section>

        <section className="disclaimer">
          <div className="shell">
            <strong>重要说明</strong>
            <p>
              骗局雷达根据一组经过选择的公开来源整理信息，可能不完整或有延迟，仅用于帮助识别常见风险，不构成法律、金融、调查或紧急处置建议。数据库里没有找到，不代表某条消息、网站、产品或联系人一定安全。
            </p>
          </div>
        </section>
      </main>
      <SiteFooter releaseId={release.release_id} />
    </>
  );
}
