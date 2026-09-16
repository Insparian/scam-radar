import type { SupabaseClient } from "@supabase/supabase-js";

import type { Database } from "@/lib/generated/database.types";
import { getSupabaseBrowserClient } from "@/lib/supabase/browser";

import { parseReviewerBootstrap } from "./parse-bootstrap";
import type {
  EvidenceDisposition,
  ReviewDecision,
  ReviewGateway,
  ReviewerQueueItem,
} from "./types";

function reviewError(message: string): Error {
  if (
    message.includes("candidate_changed") ||
    message.includes("stale_row_version")
  ) {
    return new Error("候选内容已经变化。请重新读取最新版本后再核对。");
  }
  if (message.includes("enabled_reviewer_required")) {
    return new Error("这个账号当前没有审核权限，请联系项目管理员。");
  }
  if (message.includes("decision_note_required")) {
    return new Error("请先填写决定说明。");
  }
  return new Error("数据库没有接受这次操作。请重新读取队列后再试。");
}

export class SupabaseReviewGateway implements ReviewGateway {
  constructor(
    private readonly client: SupabaseClient<Database> = getSupabaseBrowserClient(),
  ) {}

  async loadBootstrap() {
    const { data, error } = await this.client.rpc("get_reviewer_bootstrap");
    if (error) throw reviewError(error.message);
    return parseReviewerBootstrap(data);
  }

  async decide(
    item: ReviewerQueueItem,
    decision: ReviewDecision,
    note: string,
    evidenceDecisions: Record<string, EvidenceDisposition>,
  ): Promise<void> {
    const decisionNote = note.trim();
    if (!decisionNote) throw new Error("请先填写决定说明。");
    if (decisionNote.length > 500)
      throw new Error("决定说明不能超过 500 个字符。");

    if (decision === "reject" || decision === "hold") {
      const functionName =
        decision === "reject" ? "reject_review_item" : "hold_for_evidence";
      const { error } = await this.client.rpc(functionName, {
        p_review_item_id: item.id,
        p_expected_candidate_hash: item.candidateHash,
        p_decision_note: decisionNote,
      });
      if (error) throw reviewError(error.message);
      return;
    }

    if (!item.pattern || !item.policy) {
      throw new Error("缺少可核对的草稿或 Policy Engine 决定，不能批准。");
    }
    if (
      item.reviewType !== "new_pattern" &&
      item.reviewType !== "pattern_update"
    ) {
      throw new Error("这类审核项不能通过发布确认操作批准。");
    }
    if (item.policy.decisionOutcome === "blocked") {
      throw new Error("Policy Engine 已阻止这个候选，不能通过人工按钮绕过。");
    }
    if (item.evidence.length === 0) {
      throw new Error("当前候选没有证据，不能批准发布。");
    }

    const proposedEvidence = item.evidence.filter(
      (evidence) => evidence.acceptanceStatus === "proposed",
    );
    const undecided = proposedEvidence.filter(
      (evidence) => !evidenceDecisions[evidence.id],
    );
    if (undecided.length > 0) {
      throw new Error("请逐条决定所有待定证据是接受还是拒绝。");
    }

    const acceptedEvidenceIds = proposedEvidence
      .filter((evidence) => evidenceDecisions[evidence.id] === "accepted")
      .map((evidence) => evidence.id);
    const rejectedEvidenceIds = proposedEvidence
      .filter((evidence) => evidenceDecisions[evidence.id] === "rejected")
      .map((evidence) => evidence.id);

    const { error } = await this.client.rpc("confirm_policy_publication", {
      p_policy_decision_id: item.policy.id,
      p_review_item_id: item.id,
      p_draft_revision_id: item.pattern.draftRevision.id,
      p_expected_row_version: item.baseRowVersion,
      p_expected_candidate_hash: item.candidateHash,
      p_expected_content_hash: item.pattern.draftRevision.contentHash,
      p_accepted_evidence_ids: acceptedEvidenceIds,
      p_rejected_evidence_ids: rejectedEvidenceIds,
      p_decision_note: decisionNote,
    });
    if (error) throw reviewError(error.message);
  }
}
