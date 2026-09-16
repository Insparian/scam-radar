"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { formatChineseDate } from "@/lib/public-data/copy";
import { SupabaseReviewGateway } from "@/lib/review/supabase-gateway";
import type {
  EvidenceDisposition,
  ReviewDecision,
  ReviewerQueueItem,
} from "@/lib/review/types";

export function ReviewConsole() {
  const gateway = useMemo(() => new SupabaseReviewGateway(), []);
  const [items, setItems] = useState<ReviewerQueueItem[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [note, setNote] = useState("");
  const [evidenceDecisions, setEvidenceDecisions] = useState<
    Record<string, EvidenceDisposition>
  >({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    try {
      const bootstrap = await gateway.loadBootstrap();
      setItems(bootstrap.queue);
      setSelectedId((current) =>
        bootstrap.queue.some((item) => item.id === current)
          ? current
          : (bootstrap.queue[0]?.id ?? ""),
      );
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "无法读取审核队列。");
    } finally {
      setLoading(false);
    }
  }, [gateway]);

  useEffect(() => {
    void Promise.resolve().then(loadQueue);
  }, [loadQueue]);

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? items[0],
    [items, selectedId],
  );

  async function decide(decision: ReviewDecision) {
    if (!selected || submitting) return;
    setSubmitting(true);
    setMessage("");
    setError("");
    try {
      await gateway.decide(selected, decision, note, evidenceDecisions);
      setMessage(
        decision === "approve"
          ? "审核决定已写入数据库；公开网站尚未构建或部署新版本。"
          : decision === "reject"
            ? "不公开决定已写入数据库。"
            : "已标记为等待更多证据。",
      );
      setNote("");
      setEvidenceDecisions({});
      await loadQueue();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审核操作失败。");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && items.length === 0) {
    return (
      <main
        id="main-content"
        className="admin-page admin-empty-state"
        aria-busy="true"
      >
        <span className="admin-eyebrow">LOADING REVIEW QUEUE</span>
        <h1>正在读取审核队列…</h1>
      </main>
    );
  }

  if (!selected) {
    return (
      <main id="main-content" className="admin-page admin-empty-state">
        <span className="admin-eyebrow">EXCEPTION REVIEW · 0 OPEN</span>
        <h1>目前没有需要人工决定的项目</h1>
        <p>生产数据库的 reviewer 队列为空。无需为了维持产量而制造审核任务。</p>
        {error && <div className="fixture-message">{error}</div>}
      </main>
    );
  }

  const pattern = selected.pattern;
  const revision = pattern?.draftRevision;
  const policy = selected.policy;
  const approvalBlocked =
    !pattern ||
    !revision ||
    !policy ||
    !["new_pattern", "pattern_update"].includes(selected.reviewType) ||
    policy.decisionOutcome === "blocked" ||
    selected.evidence.length === 0;

  return (
    <main id="main-content" className="admin-page admin-review-page">
      <header className="admin-page-header">
        <div>
          <span className="admin-eyebrow">
            EXCEPTION REVIEW · {items.length} OPEN
          </span>
          <h1>需要人工决定</h1>
          <p>
            Policy Engine
            已完成分流。批准前必须逐条判断待定证据，并留下决定说明。
          </p>
        </div>
        <button className="admin-refresh" onClick={() => void loadQueue()}>
          重新读取
        </button>
      </header>
      {message && (
        <div className="review-message success" role="status">
          {message}
        </div>
      )}
      {error && (
        <div className="review-message error" role="alert">
          {error}
        </div>
      )}
      <div className="review-layout">
        <aside className="queue-list" aria-label="需要人工决定的项目">
          {items.map((item) => (
            <button
              className={item.id === selected.id ? "selected" : ""}
              key={item.id}
              onClick={() => {
                setSelectedId(item.id);
                setMessage("");
                setError("");
                setNote("");
                setEvidenceDecisions({});
              }}
            >
              <span
                className={`queue-dot status-${item.status}`}
                aria-hidden="true"
              />
              <span>
                <strong>
                  {item.pattern?.draftRevision.canonicalName ?? item.reviewType}
                </strong>
                <small>
                  优先级 {item.priority} · 证据{" "}
                  {item.evidenceLevelAtCreation ?? "—"} · {item.status}
                </small>
              </span>
              <b>→</b>
            </button>
          ))}
        </aside>
        <article className="review-detail">
          <div className="review-topline">
            <span>
              POLICY ENGINE → {policy?.decisionOutcome ?? "missing decision"}
            </span>
            <span>优先级 {selected.priority}</span>
          </div>
          <section className="policy-route" aria-label="Policy Engine 路由">
            <div>
              <span>确定性判定</span>
              <strong>{policy?.rulesOutcome ?? "不可批准"}</strong>
            </div>
            <p>
              {(policy?.reasonCodes ?? selected.reasonCodes).join(" · ")}
              <br />
              {policy?.executionMode === "live"
                ? "当前策略记录来自 live 模式；数据库仍会重新验证是否具备授权。"
                : "影子模式不会授予自动发布权限；本次只能由 reviewer 明确决定。"}
            </p>
          </section>

          {!revision ? (
            <section className="review-block">
              <h2>这个队列项没有可审核的模式草稿</h2>
              <p>可以选择不公开或等待更多证据；不能批准。</p>
            </section>
          ) : (
            <>
              <h2>{revision.canonicalName}</h2>
              <p className="review-summary">{revision.oneSentenceSummary}</p>
              <div className="review-metrics">
                <div>
                  <span>Heat</span>
                  <strong>
                    {selected.heat?.score ?? selected.heatAtCreation ?? "—"}
                  </strong>
                  <small>{selected.heat?.scoreVersion ?? "创建时快照"}</small>
                </div>
                <div>
                  <span>Evidence</span>
                  <strong>{revision.evidenceLevel}</strong>
                  <small>
                    {revision.publicEvidenceLabel ?? "无公开证据标签"}
                  </small>
                </div>
                <div>
                  <span>最后变化</span>
                  <strong>
                    {formatChineseDate(
                      revision.lastMaterialChangeAt ?? revision.lastSeenAt,
                    )}
                  </strong>
                  <small>{revision.riskType}</small>
                </div>
              </div>
            </>
          )}

          <section className="review-block">
            <div className="review-block-heading">
              <h3>证据与独立性</h3>
              <span>{selected.evidence.length} 个来源</span>
            </div>
            {selected.evidence.length === 0 ? (
              <p className="review-muted">没有可核对的证据，不能批准公开。</p>
            ) : (
              selected.evidence.map((evidence, index) => {
                const disposition = evidenceDecisions[evidence.id];
                return (
                  <article className="review-evidence" key={evidence.id}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>
                        {evidence.source.name} · {evidence.source.authorityTier}
                      </strong>
                      <p>{evidence.claimSummary}</p>
                      <a
                        href={evidence.source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {evidence.source.title} ↗
                      </a>
                      <small>
                        family {evidence.evidenceFamilyId ?? "未分组"} · origin{" "}
                        {evidence.originGroupKey}
                      </small>
                      {evidence.acceptanceStatus === "proposed" ? (
                        <div
                          className="evidence-decision"
                          role="group"
                          aria-label="证据决定"
                        >
                          <button
                            className={
                              disposition === "accepted" ? "selected" : ""
                            }
                            onClick={() =>
                              setEvidenceDecisions((current) => ({
                                ...current,
                                [evidence.id]: "accepted",
                              }))
                            }
                          >
                            接受为依据
                          </button>
                          <button
                            className={
                              disposition === "rejected"
                                ? "selected reject"
                                : ""
                            }
                            onClick={() =>
                              setEvidenceDecisions((current) => ({
                                ...current,
                                [evidence.id]: "rejected",
                              }))
                            }
                          >
                            不采用
                          </button>
                        </div>
                      ) : (
                        <span className="evidence-existing-status">
                          已记录：{evidence.acceptanceStatus}
                        </span>
                      )}
                    </div>
                  </article>
                );
              })
            )}
          </section>

          {revision && (
            <section className="review-block">
              <div className="review-block-heading">
                <h3>候选公开措辞</h3>
                <span>尚未进入公开 release</span>
              </div>
              <div className="public-preview">
                <span>现在先做什么</span>
                <strong>{revision.whatToDo[0] ?? "尚未提供行动建议"}</strong>
                <p>{revision.warningSigns.slice(0, 2).join("；")}</p>
              </div>
            </section>
          )}

          <section className="review-versions" aria-label="行为版本">
            <span>Candidate {selected.candidateSchemaVersion}</span>
            <span>Revision {revision?.schemaVersion ?? "missing"}</span>
            <span>Policy {policy?.policyVersion ?? "missing"}</span>
            <span>Gate {policy?.gateVersion ?? "missing"}</span>
          </section>
          <label className="decision-note">
            决定说明
            <textarea
              value={note}
              maxLength={500}
              onChange={(event) => setNote(event.target.value)}
              placeholder="记录接受、拒绝或等待更多证据的理由"
            />
          </label>
          <div className="primary-actions">
            <button
              disabled={submitting || approvalBlocked}
              onClick={() => void decide("approve")}
            >
              {selected.reviewType === "pattern_update"
                ? "确认更新"
                : "批准新记录"}
            </button>
            <button
              className="danger-action"
              disabled={submitting}
              onClick={() => void decide("reject")}
            >
              不公开
            </button>
          </div>
          <button
            className="hold-action"
            disabled={submitting}
            onClick={() => void decide("hold")}
          >
            先保留，等待更多证据
          </button>
          {approvalBlocked && (
            <p className="review-action-note">
              缺少草稿、Policy Engine 决定，或策略结果为
              blocked，因此批准按钮已关闭。
            </p>
          )}
        </article>
      </div>
    </main>
  );
}
