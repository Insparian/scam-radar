export type RiskType = "confirmed_scam" | "risk_alert";
export type LegalStatus =
  | "warning"
  | "reported_case"
  | "enforcement"
  | "charge"
  | "judgment"
  | "unknown";
export type EvidenceLevel = "A" | "B" | "C" | "D";
export type HeatBand = "immediate" | "recent" | "observe" | "database";

export interface HeatSnapshot {
  score: number;
  band: HeatBand;
  active_attention: boolean;
  as_of: string;
  version: "scam-heat-v0.1";
  components: {
    target_relevance: number;
    freshness: number;
    harm: number;
    spread: number;
    novelty: number;
  };
}

export interface EvidenceItem {
  institution: string;
  authority_tier: "A1" | "A2" | "B";
  date: string;
  title: string;
  url: string;
  claim_summary: string;
}

export interface TimelineItem {
  date: string;
  title: string;
  material: boolean;
}

export interface PublicPattern {
  id: string;
  revision_id: string;
  slug: string;
  risk_type: RiskType;
  legal_status: LegalStatus;
  evidence_level: EvidenceLevel;
  evidence_label: string;
  canonical_name: string;
  short_name: string;
  aliases: string[];
  one_sentence_summary: string;
  immediate_action: string;
  mechanism_intro: string;
  mechanism_steps: string[];
  warning_signs: string[];
  what_to_do: string[];
  categories: string[];
  search_terms: string[];
  regions: string[];
  first_seen_at: string;
  last_material_change_at: string;
  last_reviewed_at: string;
  heat: HeatSnapshot;
  timeline: TimelineItem[];
  evidence: EvidenceItem[];
}

export interface PublicRelease {
  schema_version: 1;
  release_id: string;
  release_no: number;
  generated_at: string;
  as_of: string;
  patterns: PublicPattern[];
}

export interface SearchIndexItem {
  slug: string;
  canonical_name: string;
  aliases: string[];
  keywords: string[];
}
