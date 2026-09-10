# Contributing to Scam Radar

Scam Radar welcomes improvements that make evidence easier to verify, reduce noise, or help ordinary families recognize a scam before harm occurs.

## Before opening a change

1. Read `AGENTS.md`, `docs/North Star.md`, and `docs/open-source-boundary.md`.
2. Open an issue before a new feature, architecture change, dependency, source activation, policy change, or public-copy change that could affect accusations or safety.
3. Keep examples synthetic. Never submit victim personal information, production rows, raw source pages, credentials, private reviewer notes, or unpublished allegations.
4. Do not make application tests contact external services. Use fixtures and recorded responses.

## Development checks

Use the repository's stable commands:

```bash
make bootstrap
make check
make test
make eval
make demo
make open-source-audit
```

Prompt, schema, model, taxonomy, scoring, or policy behavior changes need matching recorded-response eval coverage and a behavior manifest update. Database changes are forward-only migrations. Generated database types must never be edited by hand.

## Pull requests

Explain the user problem, why the change belongs now, its evidence or test basis, and any new data movement. Keep unrelated edits separate. A passing test suite does not by itself authorize real collection, AI calls, production writes, deployment, or DNS changes.

By intentionally submitting a contribution, you agree that it is provided under the repository's Apache-2.0 license.
