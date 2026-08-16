import Link from "next/link";

import { formatChineseDate, heatLabel } from "@/lib/public-data/copy";
import type { PublicPattern } from "@/lib/public-data/types";

export function PatternCard({
  pattern,
  compact = false,
}: {
  pattern: PublicPattern;
  compact?: boolean;
}) {
  return (
    <article className={`pattern-card heat-${pattern.heat.band}`}>
      <div className="card-meta">
        <span className="attention-label">
          <span aria-hidden="true" />
          {heatLabel(pattern.heat.band, pattern.heat.active_attention)}
        </span>
        <span className="evidence-chip">
          证据 {pattern.evidence_level} · {pattern.evidence_label}
        </span>
      </div>
      <h3>
        <Link href={`/scam/${pattern.slug}/`}>{pattern.canonical_name}</Link>
      </h3>
      <p>{pattern.one_sentence_summary}</p>
      {!compact && (
        <div className="do-first">
          <strong>现在先做：</strong>
          {pattern.immediate_action}
        </div>
      )}
      <div className="card-footer">
        <span>
          最近变化 {formatChineseDate(pattern.last_material_change_at)}
        </span>
        <Link className="text-link" href={`/scam/${pattern.slug}/`}>
          看清这个套路 <span aria-hidden="true">→</span>
        </Link>
      </div>
    </article>
  );
}
