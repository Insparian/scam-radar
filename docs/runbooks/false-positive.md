# False positive and urgent unpublish

## Current offline behavior

Use fixtures to test the state transitions and next-release exclusion. No production takedown or Cloudflare removal has been exercised yet.

## Live response — activation only

1. An enabled reviewer confirms the problem and records the reason. Mark `takedown_requested`; do not claim the page is already gone.
2. Prepare an urgent immutable release that omits the pattern. Do not edit/delete the approved revision, evidence, or audit history.
3. Move the UI through truthful states: `takedown_requested` → `removal_deploying` → `removed_from_current_site` only after verification.
4. Follow the exact-artifact path in [deploy and rollback](deploy-and-rollback.md). Urgency may bypass the normal collection interval, never release checks or human identity.
5. Verify on the canonical site:
   - home and search no longer include the pattern;
   - the detail route returns the intended 404/410 behavior;
   - page, search index, and `release.json` expose the same new `release_id`.
6. Record reviewer, reason, timestamps, prior revision, evidence/model/prompt/Heat context, removal release, artifact hash, and deployment ID.

An old preview URL or CDN copy may remain reachable. Record that limitation. Purge/removal beyond the normal supported rollback path is destructive and needs explicit approval.

## Root-cause follow-up

Determine whether source quality, extraction, evidence-family grouping, Evidence Gate, legal wording, Heat, reviewer UI, or human review failed. Add the case to the Gold Set before approving a corrected new revision. Run the relevant evals and complete offline suite.

Do not contact an alleged perpetrator, promise fund recovery, erase internal history, or expose victim/reviewer identity.
