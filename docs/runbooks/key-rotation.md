# Key rotation

## When to rotate

Rotate on suspected exposure, unexpected authentication use, staff/access change, provider instruction, or planned credential expiry. Never paste the suspect value into chat, logs, tickets, commands, or screenshots.

## Immediate response

1. Pause only the affected path: collection/AI/deploy or migration. If scope is unclear, pause all external workflows; the static site stays available.
2. Identify the credential by name, owner, environment, last known use, and first six characters at most. Preserve audit metadata, not the secret.
3. Create a replacement with the narrowest supported permission and optional expiry/IP restriction.
4. Update the specific GitHub Encrypted Secret or ignored local secret. Do not place credentials at workflow scope.
5. Run the smallest safe check, then revoke/disable the old credential. Creating a new key does not always revoke a legacy one.
6. Review logs and releases for misuse, then re-enable gradually and record the rotation.

## Credential-specific notes

- **Supabase publishable key:** public by design; security still depends on grants/RLS. Rotate if project policy requires it and retest anon/reviewer boundaries.
- **Supabase secret/service role:** bypasses RLS. Rotate immediately on suspicion; retest worker/exporter access and prove it cannot satisfy human approval. Prefer current `sb_secret_...` for new projects; explicitly disable old legacy keys.
- **Supabase access token / DB password:** used only by protected migration/recovery paths. Rotate and verify no normal worker/web job receives it.
- **Gemini key:** update only the live-eval/AI step, keep AI disabled during validation, and use a capped non-publishing check.
- **Cloudflare token:** use a token limited to one account plus Pages Write/Edit, never a Global API Key. Cloudflare does not document per-Pages-project resource scope; use account isolation if required.
- **GitHub token:** prefer job-scoped automatic tokens and minimum permissions; rotate any separate token through GitHub's supported flow.

After rotation, run secret scanning, verify no compiled static asset contains the old/new sentinel, and document user impact. If data access may have occurred, treat it as a security incident rather than closing at “key changed.”
