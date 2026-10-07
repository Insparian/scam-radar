# Decision 013 — Thin Goal Router coordinator

- **What:** Make Sol a thin coordinator with one active worker by default, bounded context, delegated reconnaissance and verification, and a project-local tool guard.
- **Why now:** Decision 012 measured about 1.21 million input tokens in 6 minutes 33 seconds; most Sol tool work happened before the first delegation while it loaded project history and performed reconnaissance.
- **Problem it solves:** Preserve durable mission ownership without making Sol repeatedly scan, implement, test, or reload the full repository.
- **Alternative considered:** Strengthen delegation wording while keeping the existing coordinator responsibilities. This was rejected because the current skill already encourages delegation, yet Sol still performed 27 tool calls before spawning Terra.
- **North Star check:** The change keeps project authorization and final accountability with Sol while moving repository labor and deterministic verification to lower-cost workers.

This decision supersedes the generic single-agent sentence in Decision 011 only when Goal Router is explicitly invoked. Project security, privacy, data, activation, deployment, and approval boundaries remain authoritative.
