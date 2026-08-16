import type { PublicPattern } from "@/lib/public-data/types";

export type FixtureDecision = "create" | "update" | "merge" | "reject" | "hold";

export interface FixtureReviewItem {
  id: string;
  reviewType: "new_pattern" | "pattern_update";
  status: "pending" | "approved" | "rejected" | "needs_evidence";
  priority: number;
  reasonCodes: string[];
  pattern: PublicPattern;
  extractionUncertainties: string[];
  modelVersion: string;
  promptVersion: string;
  schemaVersion: string;
}

export interface ReviewGateway {
  decide(
    itemId: string,
    decision: FixtureDecision,
    note: string,
  ): Promise<{ ok: true; fixtureOnly: true }>;
}
