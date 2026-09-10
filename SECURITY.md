# Security Policy

## Reporting a vulnerability

Send security reports privately to `rui@insparian.com`. Include the affected component, likely impact, and the smallest safe reproduction you can provide. Do not include live credentials, victim information, production database exports, malicious binaries, or source material that is not already public and necessary to understand the issue.

Please do not open a public issue before a vulnerability that could expose private data, bypass review or Policy Engine controls, mutate immutable releases, or publish without authority has been contained.

## Scope priorities

The highest-priority boundaries are:

- anonymous access to private Supabase data;
- reviewer authentication or authorization bypass;
- worker credentials impersonating a human decision;
- shadow policy decisions gaining live publication authority;
- mutation of verified revisions, audit events, or public releases;
- secrets or private source text entering a static export, log, artifact, or repository;
- public search queries leaving the visitor's browser.

Offline fixtures and intentionally disabled cloud workflows are not production services. Reports should distinguish a design gap from a currently exploitable live path.

## Disclosure

We will acknowledge reports when practical, investigate impact, and coordinate a proportionate disclosure after users and data are protected. Do not access, alter, or retain more data than is necessary to demonstrate the issue.
