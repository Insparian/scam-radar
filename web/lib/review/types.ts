import type { Json } from "@/lib/generated/database.types";

export type ReviewDecision = "approve" | "reject" | "hold";
export type EvidenceDisposition = "accepted" | "rejected";

export interface ReviewerIdentity {
  userId: string;
  role: "reviewer" | "admin";
}

export interface ReviewerPolicyDecision {
  id: string;
  surface: "public_database" | "distribution";
  policyVersion: string;
  gateVersion: string;
  gateOutcome: string;
  rulesOutcome: "safe_to_automate" | "review_required" | "blocked";
  decisionOutcome: "safe_to_automate" | "review_required" | "blocked";
  executionMode: "shadow" | "live";
  publicationAuthorized: boolean;
  modelConfidence: number | null;
  modelConfidenceDowngrade: boolean;
  reasonCodes: string[];
  evaluatedAt: string;
}

export interface ReviewerEvidence {
  id: string;
  evidenceType: string;
  originGroupKey: string;
  evidenceFamilyId: string | null;
  claimSummary: string;
  eventDate: string | null;
  region: string | null;
  isMaterialUpdate: boolean;
  acceptanceStatus: "proposed" | "accepted" | "rejected";
  lastVerifiedAt: string | null;
  sourceStatus: string;
  source: {
    name: string;
    authorityTier: string;
    title: string;
    url: string;
    publishedAt: string | null;
  };
}

export interface ReviewerDraftRevision {
  id: string;
  schemaVersion: string;
  contentHash: string;
  canonicalName: string;
  shortName: string | null;
  patternType: string;
  riskType: string;
  evidenceLevel: string;
  legalStatus: string;
  publicEvidenceLabel: string | null;
  oneSentenceSummary: string;
  targetPopulation: string[];
  contactChannels: string[];
  impersonatedIdentities: string[];
  hooks: string[];
  commonPhrases: string[];
  pressureTactics: string[];
  requestedActions: string[];
  moneyPaths: string[];
  technologyUsed: string[];
  warningSigns: string[];
  whatToDo: string[];
  regions: string[];
  firstSeenAt: string;
  lastSeenAt: string;
  lastMaterialChangeAt: string | null;
}

export interface ReviewerPattern {
  id: string;
  slug: string;
  lifecycleStatus: string;
  rowVersion: number;
  draftRevision: ReviewerDraftRevision;
}

export interface ReviewerQueueItem {
  id: string;
  reviewType: string;
  status: "pending" | "in_review" | "needs_evidence";
  priority: number;
  heatAtCreation: number | null;
  evidenceLevelAtCreation: string | null;
  reasonCodes: string[];
  candidateSchemaVersion: string;
  candidateHash: string;
  baseRowVersion: number;
  createdAt: string;
  pattern: ReviewerPattern | null;
  policy: ReviewerPolicyDecision | null;
  heat: {
    score: number;
    scoreVersion: string;
    asOf: string;
    breakdown: Json;
  } | null;
  evidence: ReviewerEvidence[];
}

export interface ReviewerBootstrap {
  reviewer: ReviewerIdentity;
  queue: ReviewerQueueItem[];
}

export interface ReviewGateway {
  loadBootstrap(): Promise<ReviewerBootstrap>;
  decide(
    item: ReviewerQueueItem,
    decision: ReviewDecision,
    note: string,
    evidenceDecisions: Record<string, EvidenceDisposition>,
  ): Promise<void>;
}
