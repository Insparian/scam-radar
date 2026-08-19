# False positive and urgent unpublish

## Current offline behavior

Use fixtures to test the state transitions and next-release exclusion. No production takedown or Cloudflare removal has been exercised yet.

## Live response — activation only

1. An enabled human confirms the problem and records the reason, regardless of whether the original revision used policy or human verification. Mark `takedown_requested`; do not claim the page is already gone.
2. Prepare an urgent immutable release that omits the pattern. Do not edit/delete the verified revision, evidence, policy decision, or human audit history.
3. Move the UI through truthful states: `takedown_requested` → `removal_deploying` → `removed_from_current_site` only after verification.
4. Follow the exact-artifact path in [deploy and rollback](deploy-and-rollback.md). Urgency may bypass the normal collection interval, never release checks or accountable human takedown identity.
5. Verify on the canonical site:
   - home and search no longer include the pattern;
   - the detail route returns the intended 404/410 behavior;
   - page, search index, and `release.json` expose the same new `release_id`.
6. Record reviewer, reason, timestamps, prior revision, evidence/model/prompt/Heat context, removal release, artifact hash, and deployment ID.

An old preview URL or CDN copy may remain reachable. Record that limitation. Purge/removal beyond the normal supported rollback path is destructive and needs explicit approval.

## Root-cause follow-up

Determine whether source quality, extraction, evidence-family grouping, Evidence Gate, Policy Engine class/reasoning, one-way confidence downgrade, legal wording, Heat, exception UI, or human decision failed. If any live automatic class was involved, disable that class immediately and preserve its policy decision; shadow mode by itself cannot have auto-published. Add the case to the Gold Set before authorizing a corrected new revision. Run the relevant evals and complete offline suite.

Do not contact an alleged perpetrator, promise fund recovery, erase internal history, or expose victim/reviewer identity.
