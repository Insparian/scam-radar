import { getRelease } from "@/lib/public-data/load";
import type { FixtureReviewItem } from "@/lib/review/types";

import { ReviewConsole } from "./review-console";

export default function ReviewQueuePage() {
  const release = getRelease();
  const items = release.patterns
    .map((pattern, index) => {
      const shadowSafe = index === 0;
      return {
        id: `fixture-review-${index + 1}`,
        reviewType: shadowSafe ? "pattern_update" : "new_pattern",
        status: "pending",
        priority: pattern.heat.score,
        reasonCodes: shadowSafe
          ? ["shadow_confirmation_required"]
          : pattern.timeline[0]?.material
            ? ["material_change", "public_copy_review"]
            : ["public_copy_review"],
        policyOutcome: shadowSafe ? "safe_to_automate" : "review_required",
        policyVersion: "publication-policy-v0.1",
        policyReasonCodes: shadowSafe
          ? ["deterministic_policy_class_matched"]
          : [
              "first_publication_requires_review",
              "material_change_requires_review",
              "public_copy_change_requires_review",
            ],
        shadowMode: true,
        pattern,
        extractionUncertainties: shadowSafe
          ? ["没有实质内容变化；本次只演示 V0.1 影子确认"]
          : pattern.evidence.length === 1
            ? ["只有一个证据来源，需要人工确认适用措辞"]
            : ["需要人工确认两个来源是否真正独立"],
        modelVersion: "recorded-fixture-v1",
        promptVersion: "extraction-v1 + pattern-match-v1",
        schemaVersion: "v1",
      } satisfies FixtureReviewItem;
    })
    .sort((left, right) => right.priority - left.priority);
  return <ReviewConsole initialItems={items} releaseId={release.release_id} />;
}
