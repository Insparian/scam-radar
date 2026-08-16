"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { formatChineseDate } from "@/lib/public-data/copy";
import { FixtureReviewGateway } from "@/lib/review/fixture-gateway";
import type { FixtureDecision, FixtureReviewItem } from "@/lib/review/types";

const gateway = new FixtureReviewGateway();

export function ReviewConsole({
  initialItems,
  releaseId,
}: {
  initialItems: FixtureReviewItem[];
  releaseId: string;
}) {
  const [items, setItems] = useState(initialItems);
  const [selectedId, setSelectedId] = useState(initialItems[0]?.id ?? "");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0],
    [items, selectedId],
  );

  async function decide(decision: FixtureDecision) {
    if (!selected) return;
    await gateway.decide(selected.id, decision, note);
    const status =
      decision === "reject"
        ? "rejected"
        : decision === "hold"
          ? "needs_evidence"
          : "approved";
    setItems((current) =>
      current.map((item) =>
        item.id === selected.id ? { ...item, status } : item,
      ),
    );
    setMessage(
      `已在离线演示中记录“${decision}”。没有写入数据库，也没有改变公开版本 ${releaseId}。`,
    );
    setNote("");
  }

  if (!selected)
    return (
      <main id="main-content" className="admin-page">
        <h1>审核队列为空</h1>
      </main>
    );

  return (
    <main id="main-content" className="admin-page admin-review-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">
            REVIEW QUEUE ·{" "}
            {items.filter((item) => item.status === "pending").length} PENDING
          </span>
          <h1>Review Queue</h1>
          <p>先看证据和边界，再看文案是否好读。</p>
        </div>
        <div className="admin-release">
          <span>公开版本</span>
          <code>{releaseId}</code>
        </div>
      </header>
      {message && (
        <div className="fixture-message" role="status">
          {message}
        </div>
      )}
      <div className="review-layout">
        <aside className="queue-list" aria-label="审核项目">
          {items.map((item) => (
            <button
              className={item.id === selected.id ? "selected" : ""}
              key={item.id}
              onClick={() => {
                setSelectedId(item.id);
                setMessage("");
              }}
            >
              <span
                className={`queue-dot status-${item.status}`}
                aria-hidden="true"
              />
              <span>
                <strong>{item.pattern.canonical_name}</strong>
                <small>
                  Heat {item.pattern.heat.score} · 证据{" "}
                  {item.pattern.evidence_level} · {item.status}
                </small>
              </span>
              <b>→</b>
            </button>
          ))}
        </aside>
        <article className="review-detail">
          <div className="review-topline">
            <span>
              {selected.reviewType === "new_pattern"
                ? "建议创建新 Pattern"
                : "建议更新 Pattern"}
            </span>
            <span>优先级 {selected.priority}</span>
          </div>
          <h2>{selected.pattern.canonical_name}</h2>
          <p className="review-summary">
            {selected.pattern.one_sentence_summary}
          </p>
          <div className="review-metrics">
            <div>
              <span>Heat</span>
              <strong>{selected.pattern.heat.score}</strong>
              <small>
                {Object.entries(selected.pattern.heat.components)
                  .map(([key, value]) => `${key} ${value}`)
                  .join(" · ")}
              </small>
            </div>
            <div>
              <span>Evidence</span>
              <strong>{selected.pattern.evidence_level}</strong>
              <small>{selected.pattern.evidence_label}</small>
            </div>
            <div>
              <span>最后变化</span>
              <strong>
                {formatChineseDate(selected.pattern.last_material_change_at)}
              </strong>
              <small>{selected.pattern.timeline[0]?.title}</small>
            </div>
          </div>
          <section className="review-block">
            <div className="review-block-heading">
              <h3>证据与独立性</h3>
              <span>{selected.pattern.evidence.length} 个来源</span>
            </div>
            {selected.pattern.evidence.map((item, index) => (
              <article className="review-evidence" key={item.url}>
                <span>{index + 1}</span>
                <div>
                  <strong>
                    {item.institution} · {item.authority_tier}
                  </strong>
                  <p>{item.claim_summary}</p>
                  <small>
                    证据 family fixture-family-{index + 1} · origin
                    fixture-origin-{index + 1}
                  </small>
                </div>
              </article>
            ))}
          </section>
          <section className="review-block">
            <div className="review-block-heading">
              <h3>机器不确定项</h3>
            </div>
            <ul>
              {selected.extractionUncertainties.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
          <section className="review-block">
            <div className="review-block-heading">
              <h3>公开页预览</h3>
              <Link href={`/scam/${selected.pattern.slug}/`} target="_blank">
                打开完整预览 ↗
              </Link>
            </div>
            <div className="public-preview">
              <span>现在先做什么</span>
              <strong>{selected.pattern.immediate_action}</strong>
              <p>{selected.pattern.warning_signs.slice(0, 2).join("；")}</p>
            </div>
          </section>
          <section className="review-versions" aria-label="行为版本">
            <span>Model {selected.modelVersion}</span>
            <span>Prompt {selected.promptVersion}</span>
            <span>Schema {selected.schemaVersion}</span>
          </section>
          <label className="decision-note">
            决定说明（离线演示）
            <textarea
              value={note}
              maxLength={500}
              onChange={(event) => setNote(event.target.value)}
              placeholder="记录为什么接受、拒绝或需要更多证据"
            />
          </label>
          <div className="primary-actions">
            <button onClick={() => decide("update")}>Approve Update</button>
            <button onClick={() => decide("create")}>Create New Pattern</button>
            <button onClick={() => decide("merge")}>Merge</button>
            <button className="danger-action" onClick={() => decide("reject")}>
              Reject
            </button>
          </div>
          <button className="hold-action" onClick={() => decide("hold")}>
            先保留，等待更多证据
          </button>
        </article>
      </div>
    </main>
  );
}
