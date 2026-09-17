# Preserve evidence resolution provenance

- **What:** Add a forward-only, append-only evidence-resolution event ledger so every accepted or rejected evidence transition records its outcome, reason, timestamp, and honest human, policy, or `legacy_unknown` authority in the same transaction as the state change.
- **Why now:** The reviewer control plane is verified while production still contains no application rows, so the audit boundary can be completed before real evidence creates history that cannot be reconstructed honestly.
- **Problem it solves:** A rejected evidence row currently retains only its terminal status, so an operator cannot reliably answer who or what rejected it and why. That weakens correction, review, and public-claim traceability.
- **Alternative considered:** Add actor and reason columns directly to the mutable evidence row. This was rejected because a row can only describe its latest state, encourages later overwrites, and does not cleanly distinguish human and policy authority over time.
- **North Star check:** This directly supports Evidence before accusation, AI not owning factual authority, and traceable public claims. The cost is another immutable ledger and stricter transactional checks, which is appropriate before the first live evidence enters production.

Rui explicitly approved this decision by replying `proceed` on 2026-09-17.

Implemented and locally verified in `9054d2e`. Production application remains a
separate mutation checkpoint. Rui approved that checkpoint on 2026-09-18; protected
workflow run `35288862213` applied and verified the seventh migration with zero
application rows.
