# Decision 012 — Goal Router model activity diagnostic

- **What:** Install a privacy-minimized project-local Codex hook and run the existing Goal Router mission for 10–15 minutes without changing routing behavior.
- **Why now:** Sol quota consumption remained high after one successful Terra delegation, but no event-level evidence identifies which model performed the subsequent work.
- **Problem it solves:** Determine whether Sol resumes implementation, repair, or substantive verification after Terra returns, while preserving the existing offline mission and activation boundaries.
- **Alternative considered:** Immediately prohibit Sol from implementation tools. This was rejected for the diagnostic run because it would change the behavior under investigation and could block legitimate checkpoint, dispatch, and evidence-integration work.
- **North Star check:** The diagnostic supports token-efficient autonomous delivery and keeps all metadata local. It records event identity only and excludes prompts, commands, patches, code, tool results, transcripts, personal data, and environment values.

This decision authorizes only local hook installation, a bounded diagnostic run, and inspection of its local log. It does not resume external activation, production access, real collection, live model calls, deployment, backup upload, or DNS changes.
