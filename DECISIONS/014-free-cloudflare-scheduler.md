# 014 — Free Cloudflare scheduler for collection

- **What:** Use a Cloudflare Workers Free Cron Trigger to dispatch the existing one-source GitHub collection workflow; remove the GitHub schedule trigger.
- **Why now:** GitHub can disable scheduled workflows in a public repository after 60 days without repository activity, so the current schedule cannot establish durable monitoring at launch.
- **Problem it solves:** Readers and Rui need scam monitoring to keep running even when the code repository is quiet; a silently stopped scheduler leaves public information stale.
- **Alternative considered:** Keep the GitHub schedule and manually reactivate it when needed. This depends on Rui noticing a missed run and does not meet the automatic-monitoring goal.
- **North Star check:** Supports automatic, free-tier operation and keeps the existing bounded human-review pipeline. It adds a Cloudflare-to-GitHub request and a narrowly scoped token, so deployment and credential placement remain separate activation gates.

Rui replied `proceed` on 2026-10-07. This authorizes offline implementation and verification of the scheduler design. It does not authorize creating a Worker, storing a live token, dispatching a real collection run, calling a model, or changing production data.
