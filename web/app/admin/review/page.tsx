import { getRelease } from "@/lib/public-data/load";
import type { FixtureReviewItem } from "@/lib/review/types";

import { ReviewConsole } from "./review-console";

export default function ReviewQueuePage() {
  const release = getRelease();
  const items = release.patterns
    .map(
      (pattern, index) =>
        ({
          id: `fixture-review-${index + 1}`,
          reviewType: "new_pattern",
          status: "pending",
          priority: pattern.heat.score,
          reasonCodes: pattern.timeline[0]?.material
            ? ["material_change", "public_copy_review"]
            : ["public_copy_review"],
          pattern,
          extractionUncertainties:
            pattern.evidence.length === 1
              ? ["只有一个证据来源，需要人工确认适用措辞"]
              : ["需要人工确认两个来源是否真正独立"],
          modelVersion: "recorded-fixture-v1",
          promptVersion: "extraction-v1 + pattern-match-v1",
          schemaVersion: "v1",
        }) satisfies FixtureReviewItem,
    )
    .sort((left, right) => right.priority - left.priority);
  return <ReviewConsole initialItems={items} releaseId={release.release_id} />;
}
