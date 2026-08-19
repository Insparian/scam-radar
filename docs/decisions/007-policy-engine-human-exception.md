# ADR-007: Deterministic Policy Engine with human exception review

- **Status:** Accepted; **safe_to_automate** is shadow-only in V0.1
- **Date:** 2026-08-16
- **Supersedes:** The mandatory-human publication clauses in ADR-002 and ADR-004. Their RLS, evidence, AI, immutable-release, and exact-artifact boundaries remain in force.

## Decision

Insert a deterministic, versioned, fail-closed Policy Engine after the Scam Intelligence Engine. It records exactly one outcome for each candidate:

- **safe_to_automate:** the candidate matches an explicitly allowed policy class;
- **review_required:** a human must make the publication decision; or
- **blocked:** Evidence/Publish Gate failure prevents publication.

Both successful paths converge on the same database-enforced verification transaction, immutable pattern revision, publication change, exact public release, and static artifact. “Automatic publish/update” means automatic authorization into the next immutable release; it never means direct mutation of the live website.

V0.1 keeps **shadow_mode: true** and **live_auto_publish_enabled: false**. A safe-to-automate decision is stored as the action the rule engine would have taken, but it does not grant publication authority. An authenticated human still confirms it. Activating live automatic authorization requires a later explicit decision backed by measured live-data performance for one narrowly named policy class. The database activation boundary must name the exact approved `policy_version`, `policy_hash`, and `gate_version`; a boolean feature flag is not publication authority.

## V0.1 policy class

Only an update to an already-public pattern can qualify, and it must have Evidence A, no material change, no public-copy change, complete claim support, verified supporting evidence, and no named-entity risk, legal-status/evidence-level change, source regression, merge, or split. First publication and Evidence B always require review in V0.1.

Unknown policy versions, missing inputs, hash mismatch, or a condition the deterministic code cannot prove fail closed.

## Model boundary

Model outputs never create or increase publication authority. Relevance or pattern-match confidence is evaluated only after deterministic rules have established that a case would otherwise be safe to automate. Low or missing confidence may downgrade that case to review required. High confidence cannot upgrade an ineligible case, override the Evidence Gate, or turn a blocked case into a publishable one.

The Policy Engine is code plus reviewed configuration, not an LLM prompt. Its version, configuration hash, candidate hash, input hash, outcome, reason codes, shadow state, and authorization result are recorded in an append-only decision.

## Verification and time semantics

Policy and human decisions have separate immutable provenance. Automation must never impersonate a reviewer or populate a synthetic human identity.

- **evidence.last_verified_at:** when that underlying evidence was actually checked.
- **revision.verified_at:** when the immutable revision passed the Policy Engine or human verification transaction.
- **release.published_at:** when the revision became part of a public release.
- **public pattern.last_verified_at:** the minimum evidence verification timestamp across evidence supporting claims in that public revision.

The public freshness date therefore describes the oldest supporting evidence check, not an internal approval action. Public release schema v2 exposes last verified separately from published at. Evidence may be rechecked after a revision decision, so `evidence.last_verified_at` and `revision.verified_at` have no required ordering relative to each other; both must exist and be no later than the release manifest's `published_at`.

## Why

The product must compress human attention, not make every safe routine update depend permanently on a person. At the same time, the current synthetic eval is explicitly not launch-qualified. Shadow mode proves routing behavior without spending user trust before live evidence exists.

## Alternatives

- **Permanent mandatory human approval:** safe but contradicts the North Star and makes reviewer capacity an architectural bottleneck.
- **Let model confidence select automatic publication:** rejected because confidence is not factual authority and can be miscalibrated.
- **Direct worker writes to the live site:** rejected because it bypasses exact-release consistency, rollback, audit, and “verified does not mean published.”
- **Enable automatic publication immediately:** rejected because no live-data false-auto measurement currently justifies it.

## Consequences and checks

- Database tests cover policy/human provenance, append-only decisions, worker inability to impersonate a reviewer, evidence freshness aggregation, and immutable releases.
- Human publication requires a matching non-blocked Policy Decision; legacy direct approval RPCs are revoked so Policy Engine routing cannot be skipped.
- Worker tests prove high confidence cannot upgrade authority, low/unknown confidence can only downgrade, shadow decisions never authorize publication, and policy/input hashes are stable.
- Admin UI shows the Policy Engine outcome and reasons; the Review Queue is an exception surface, not a general mandatory stage.
- Runbooks treat policy regression, shadow metrics, emergency human override, and live-auto disablement as separate operational controls.
- The public site continues to read one static release and never queries Supabase at request time.
