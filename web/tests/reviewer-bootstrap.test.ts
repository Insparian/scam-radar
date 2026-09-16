import type { SupabaseClient } from "@supabase/supabase-js";
import { describe, expect, it, vi } from "vitest";

import type { Database, Json } from "@/lib/generated/database.types";
import { parseReviewerBootstrap } from "@/lib/review/parse-bootstrap";
import { SupabaseReviewGateway } from "@/lib/review/supabase-gateway";

const payload = {
  reviewer: {
    user_id: "eeeeeeee-0000-4000-8000-000000000001",
    role: "reviewer",
  },
  queue: [
    {
      id: "a0000000-0000-4000-8000-000000000001",
      review_type: "new_pattern",
      status: "pending",
      priority: 80,
      heat_at_creation: 78,
      evidence_level_at_creation: "A",
      reason_codes: ["eligible_for_review"],
      candidate_schema_version: "review-candidate-v1",
      candidate_hash: "2".repeat(64),
      base_row_version: 1,
      created_at: "2026-08-16T00:00:00Z",
      pattern: {
        id: "50000000-0000-4000-8000-000000000001",
        slug: "fixture-pattern",
        lifecycle_status: "review_ready",
        row_version: 1,
        draft_revision: {
          id: "60000000-0000-4000-8000-000000000001",
          schema_version: "pattern-revision-v1",
          content_hash: "f".repeat(64),
          canonical_name: "测试骗局",
          short_name: null,
          pattern_type: "impersonation",
          risk_type: "confirmed_scam",
          evidence_level: "A",
          legal_status: "reported_case",
          public_evidence_label: "警方通报的诈骗案件",
          one_sentence_summary: "测试摘要",
          target_population: ["older_adults"],
          contact_channels: ["phone_call"],
          impersonated_identities: ["community_worker"],
          hooks: ["benefit"],
          common_phrases: ["测试话术"],
          pressure_tactics: ["urgency"],
          requested_actions: ["transfer_money"],
          money_paths: ["bank_transfer"],
          technology_used: [],
          warning_signs: ["索取验证码"],
          what_to_do: ["立即挂断"],
          regions: ["CN-XX"],
          first_seen_at: "2026-08-14T00:00:00Z",
          last_seen_at: "2026-08-15T00:00:00Z",
          last_material_change_at: "2026-08-15T00:00:00Z",
        },
      },
      policy: {
        id: "d0000000-0000-4000-8000-000000000001",
        surface: "public_database",
        policy_version: "publication-policy-v0.1",
        gate_version: "publication-gate-v0.1",
        gate_outcome: "eligible_for_policy",
        rules_outcome: "review_required",
        decision_outcome: "review_required",
        execution_mode: "shadow",
        publication_authorized: false,
        model_confidence: 0.9,
        model_confidence_downgrade: false,
        reason_codes: ["first_publication_requires_review"],
        evaluated_at: "2026-08-16T00:00:00Z",
      },
      heat: {
        score: 78,
        score_version: "scam-heat-v0.1",
        as_of: "2026-08-16",
        breakdown: { total: 78 },
      },
      evidence: [
        {
          id: "70000000-0000-4000-8000-000000000001",
          evidence_type: "official_notice",
          origin_group_key: "fixture-origin",
          evidence_family_id: "71000000-0000-4000-8000-000000000001",
          claim_summary: "测试证据",
          event_date: "2026-08-14",
          region: "CN-XX",
          is_material_update: true,
          acceptance_status: "proposed",
          last_verified_at: "2026-08-15T00:00:00Z",
          source_status: "available",
          source: {
            name: "测试警方",
            authority_tier: "A1",
            title: "测试通报",
            url: "https://example.invalid/notice",
            published_at: "2026-08-14T00:00:00Z",
          },
        },
      ],
    },
  ],
} satisfies Json;

describe("reviewer bootstrap", () => {
  it("parses the narrow reviewer RPC payload", () => {
    const result = parseReviewerBootstrap(payload);
    expect(result.reviewer.role).toBe("reviewer");
    expect(result.queue[0]?.pattern?.draftRevision.canonicalName).toBe(
      "测试骗局",
    );
    expect(result.queue[0]?.evidence[0]?.source.authorityTier).toBe("A1");
  });

  it("rejects an unexpected reviewer role", () => {
    expect(() =>
      parseReviewerBootstrap({
        reviewer: { user_id: "id", role: "service_role" },
        queue: [],
      }),
    ).toThrow("reviewer_bootstrap_invalid:reviewer.role");
  });

  it("requires an explicit decision for every proposed evidence item", async () => {
    const rpc = vi.fn();
    const client = { rpc } as unknown as SupabaseClient<Database>;
    const gateway = new SupabaseReviewGateway(client);
    const item = parseReviewerBootstrap(payload).queue[0]!;

    await expect(
      gateway.decide(item, "approve", "reviewed", {}),
    ).rejects.toThrow("请逐条决定所有待定证据");
    expect(rpc).not.toHaveBeenCalled();
  });

  it("rejects approval for a non-publication review type", async () => {
    const rpc = vi.fn();
    const client = { rpc } as unknown as SupabaseClient<Database>;
    const gateway = new SupabaseReviewGateway(client);
    const item = {
      ...parseReviewerBootstrap(payload).queue[0]!,
      reviewType: "evidence_conflict",
    };

    await expect(
      gateway.decide(item, "approve", "reviewed", {}),
    ).rejects.toThrow("这类审核项不能通过发布确认操作批准");
    expect(rpc).not.toHaveBeenCalled();
  });

  it("rejects approval without evidence", async () => {
    const rpc = vi.fn();
    const client = { rpc } as unknown as SupabaseClient<Database>;
    const gateway = new SupabaseReviewGateway(client);
    const item = {
      ...parseReviewerBootstrap(payload).queue[0]!,
      evidence: [],
    };

    await expect(
      gateway.decide(item, "approve", "reviewed", {}),
    ).rejects.toThrow("当前候选没有证据，不能批准发布");
    expect(rpc).not.toHaveBeenCalled();
  });

  it("sends approval only through the human confirmation RPC", async () => {
    const rpc = vi.fn().mockResolvedValue({ data: "revision-id", error: null });
    const client = { rpc } as unknown as SupabaseClient<Database>;
    const gateway = new SupabaseReviewGateway(client);
    const item = parseReviewerBootstrap(payload).queue[0]!;
    const evidenceId = item.evidence[0]!.id;

    await gateway.decide(item, "approve", "Evidence checked.", {
      [evidenceId]: "accepted",
    });

    expect(rpc).toHaveBeenCalledOnce();
    expect(rpc).toHaveBeenCalledWith("confirm_policy_publication", {
      p_policy_decision_id: item.policy!.id,
      p_review_item_id: item.id,
      p_draft_revision_id: item.pattern!.draftRevision.id,
      p_expected_row_version: 1,
      p_expected_candidate_hash: "2".repeat(64),
      p_expected_content_hash: "f".repeat(64),
      p_accepted_evidence_ids: [evidenceId],
      p_rejected_evidence_ids: [],
      p_decision_note: "Evidence checked.",
    });
  });
});
