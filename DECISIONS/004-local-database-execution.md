# Run the database contract in an isolated local engine

- **What:** Add a local-only Supabase/PostgreSQL execution lane for migrations and transactional security tests.
- **Why now:** The Policy Engine now controls a publication boundary. Static SQL inspection proves intent, but cannot prove that PostgreSQL triggers, RLS, grants, locks, and RPC transactions enforce it together.
- **Problem it solves:** Before any real evidence can be accepted, Rui needs evidence that a worker cannot publish from shadow mode, cannot impersonate a reviewer, cannot use an unapproved policy tuple, and cannot mutate an immutable release.
- **Alternative considered:** Continue with fixture and text-based database tests only. That is faster today, but it cannot exercise role isolation or transactional trigger behavior, so it leaves the highest-risk claims unproven.
- **North Star check:** This keeps public information conservative and traceable. It runs only synthetic `.invalid` fixtures on the developer's machine: no collection, AI call, production database connection, deployment, or new application data flow.

## Tooling boundary

Use Rancher Desktop with its Moby/dockerd engine and Kubernetes disabled, plus the
official Supabase CLI, only as local developer tooling. Rancher Desktop is Apache-2.0
licensed and Supabase explicitly lists it as a Docker-compatible runtime; selecting Moby
provides the Docker API and CLI needed by the Supabase CLI without Docker Desktop's
commercial-license question. The checked local CLI resolution is `2.115.0`, run
temporarily through `npx`; it is not added to `package.json`, Python dependencies, a
production image, or a runtime path. The lighter alternative is a standalone local
PostgreSQL instance, but it would not exercise the Supabase role/JWT layout that the
release contract relies on. Colima remains a technically compatible but non-listed
alternative, so it is not the default verification engine.

The execution suite must create its own disposable local database, apply all migrations
from zero, run positive and negative RPC transactions, and leave production systems
untouched. The existing `make check` generated-type comparison remains part of the full
verification handoff alongside this runtime database test.
