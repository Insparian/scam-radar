# ADR-003: Ephemeral Python batch worker

- **Status:** Accepted
- **Date:** 2026-08-16

## Decision

Implement collection and intelligence processing as a Python package invoked by short-lived GitHub Actions jobs. There is no daemon, queue server, VPS, or always-on API.

Each run:

1. validates versioned configuration and kill switches;
2. acquires a database lease and records a `pipeline_run`;
3. isolates each source, uses bounded work/call/time caps, and persists successful source results independently;
4. performs idempotent normalize/dedup/AI-proposal/gate/score/queue stages;
5. commits cursors only after source success; and
6. releases the lease and writes a redacted summary.

Use three `Asia/Shanghai` schedules at minute 17 plus `workflow_dispatch`. Scheduled execution is best-effort; manual dispatch and persisted backlog are the recovery path, not assumptions of real-time delivery.

## Why

This product needs periodic compression of a bounded source set, not low-latency request serving. Python has a strong parsing/validation/test ecosystem and keeps policy code readable. Ephemeral jobs minimize idle cost and ensure the prior public release survives a worker failure.

## Alternatives

- **TypeScript worker:** one language across the repository, but weaker benefit for text/HTML processing and would couple public UI release cadence to pipeline tooling.
- **Always-on service with a queue:** better real-time throughput, but the product explicitly does not promise real-time coverage and the operational surface would dominate V0.1.
- **One large shell workflow:** fewer package files, but poor unit-testability, retries, type boundaries, and idempotency.

## Consequences and checks

- Python and TypeScript create two toolchains; root `make` commands hide that complexity from Rui.
- The database, not runner disk, owns durable state. `work/` is disposable.
- A schedule may be delayed or dropped. Alerts must show exact review dates and never claim “live” coverage.
- GitHub says schedules run from the latest default-branch commit, can be delayed at high load, and may be disabled after 60 inactive days in public repositories. The workflow therefore runs away from minute zero and has a manual recovery path.
- Application tests deny outbound network except localhost and inject HTTP transports.

## Source

- [GitHub Actions scheduled workflow behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
