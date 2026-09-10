# ADR-006: Minimal dependency set for the offline V0.1

- **Status:** Accepted for scaffolding; external integrations remain disabled
- **Date:** 2026-08-16
- **Scope:** `web/`, `worker/`, local database tests, and repository tooling

## Context

Scam Radar needs two small applications: a static Next.js site/reviewer client and a scheduled Python text-processing worker. Dependencies are justified only when they remove material security, correctness, parsing, or test risk. The lockfiles created in Task 3 will pin the full transitive graph; this ADR records the intended direct dependencies before anything is installed.

Version policy:

- Pin runtime/tool versions and commit both lockfiles.
- Use the stable major/minor families below. Resolve an exact non-prerelease patch during bootstrap and record it in `package-lock.json` or `worker/uv.lock`.
- Do not run unattended major upgrades. A major upgrade requires this review to be amended and the complete offline suite to pass.
- The registry observations below are from 2026-08-16. The important compatibility floor is Node 22+: the current `@supabase/supabase-js` package declares Node `>=22`, while Next.js 16 declares Node `>=20.9`.

Implementation note after Task 11: the offline lockfiles intentionally contain only packages exercised by the offline build. Network-enabling runtime SDKs remain reviewed activation candidates, not installed dependencies. This keeps a package choice from silently becoming an enabled data path.

## Runtime and package managers

| Dependency | Version target | Purpose | Maintenance signal | Lighter alternative | User/runtime impact |
|---|---:|---|---|---|---|
| Node.js | 24.x LTS | Build and test the static site | Active LTS line; supported by both selected web runtime packages | Node 22 LTS | Build/CI only after static export; no server runs for users |
| npm | version bundled with pinned Node 24 | One Node package manager and one lockfile | Maintained with Node; avoids another bootstrap tool | pnpm or Yarn | No browser impact; slightly slower installs are acceptable at V0.1 scale |
| Python | 3.13.x | Run the batch worker and evals | Stable CPython line with broad wheel support | Python 3.14 | Choosing 3.13 reduces native-wheel and type-tool churn; no public-site runtime |
| uv | latest stable `0.x` at bootstrap, then pinned | Reproducible Python resolution, lock, and commands | Actively maintained by Astral with first-party docs | `venv` + `pip-tools` | Faster local/CI setup; no application data leaves the device |

## Web application

| Dependency | Version target | Purpose | Maintenance signal | Lighter alternative | User/runtime impact |
|---|---:|---|---|---|---|
| `next` | `16.3.1` | App Router, build-time rendering, routing, metadata, and static export | Current stable npm release; Vercel-maintained with registry provenance | Vite + a hand-built static router/exporter | Adds framework build weight, but emits portable static files and avoids a user-facing server |
| `react`, `react-dom` | `19.2.8` | Accessible component UI and client-only reviewer interactions | Current matching stable npm releases; Meta-maintained | Plain HTML/DOM | Small browser runtime cost on interactive pages; public pages should remain mostly server-rendered HTML |
| `@supabase/supabase-js` | `2.112.3` activation candidate; not in the offline lock | Reviewer PKCE Auth and calls to narrow review RPCs after activation | Current stable vendor SDK release; Supabase-maintained | Handwritten `fetch` for Auth/PostgREST | When approved, load only in admin chunks; public content/search must not call Supabase |

No production CSS framework, icon library, state library, form library, date library, search library, or client schema library is approved for V0.1. Use CSS, inline project-owned SVG, React state, `Intl`, native normalized matching, generated database types, and exporter-side release validation. Add one only after a concrete failure demonstrates the need.

## Python worker

| Dependency | Version target | Purpose | Maintenance signal | Lighter alternative | User/runtime impact |
|---|---:|---|---|---|---|
| `pydantic` | `>=2.13,<3` | Typed settings and provider-neutral request/result validation | Production/stable classifier and active 2.x releases | Dataclasses plus manual validation | Fails malformed internal/AI data early; modest worker-only install cost |
| `httpx` | `>=0.28,<1` activation candidate; not in the offline lock | Injectible live HTTP transport for collectors and Supabase REST/RPC | Mature Encode project with maintained docs/tests | Standard-library `urllib` | No source or database network path exists in the offline worker |
| `feedparser` | `>=6.0,<7` | Tolerant RSS/Atom parsing | Mature, low-churn specialist library | XML parsing by hand | Worker-only; reduces missed items from imperfect feeds |
| `beautifulsoup4` | `>=4.14,<5` | Conservative HTML selection and cleanup | Long-lived, actively released project | `html.parser` directly | Worker-only; clearer source-specific parsers |
| `lxml` | `>=6,<7` | Fast, robust HTML/XML parser used by collectors | Mature project with current wheels | Standard-library XML/HTML parsers | Native wheel increases install size; bounded batch runs become faster and more tolerant |
| `PyYAML` | `>=6,<7` | Read reviewed source/model/taxonomy/scoring configuration | Mature, stable package | Store every config as JSON | Worker-only; keeps reviewed behavior files human-readable; always use safe loading |
| `jsonschema` | `>=4.25,<5` | Validate versioned AI contracts independently of SDK/model objects | Actively maintained reference implementation | Pydantic-only schemas | Worker-only; prevents a provider-specific schema from silently becoming the contract |
| `google-genai` | `>=1,<2` activation candidate; not in the offline lock | Gemini adapter after external activation | Google-maintained official SDK with current structured-output examples | Direct REST through `httpx` | No Gemini client can be constructed in the offline worker |

The Python Supabase client is intentionally not selected. The worker already needs `httpx`, and its database surface will be a small typed REST/RPC adapter. This avoids installing Auth, Realtime, Storage, and Functions clients that the batch worker does not use.

## Test and development dependencies

| Dependency | Version target | Purpose | Maintenance signal | Lighter alternative | User/runtime impact |
|---|---:|---|---|---|---|
| `typescript` | `5.9.3` initially | Strict web type checking | Microsoft-maintained stable 5.x line | JavaScript + JSDoc | Build-only. We deliberately do not adopt TypeScript 7 on day one; ecosystem compatibility matters more than newest-major features |
| `eslint`, `eslint-config-next` | latest versions compatible with Next 16.3, then exact lock | Next/React correctness linting | Core ecosystem/vendor-maintained | TypeScript compiler alone | Build-only; catches unsafe browser/server boundary mistakes |
| `prettier` | stable 3.x | Deterministic formatting | Mature and actively maintained | Manual formatting | Build-only; reduces review noise |
| `vitest` | stable 4.x | Fast deterministic library and release-contract tests | Active Vite ecosystem | Node test runner | Dev/CI only; the current tests do not need a simulated DOM |
| `jsdom`, `@testing-library/*` | deferred until a component interaction requires them | Browser-like component testing | Established projects | Pure-function tests plus Playwright | Avoids unused test weight; Playwright currently covers user-visible interactions |
| `@playwright/test` | `1.62.1` initially | Real-browser public/admin flows and static-output checks | Current Microsoft-maintained stable npm release | Manual browser checks | Downloads test browsers in bootstrap/CI; never ships to users |
| `@axe-core/playwright` | stable 4.x | Automated high-signal accessibility checks | Deque-maintained integration around axe-core | Only manual WCAG review | Dev/CI only; complements, not replaces, keyboard/manual testing |
| `pytest`, `pytest-cov` | stable 9.x / 7.x | Worker unit/integration tests and coverage | Mature, actively maintained Python tooling | `unittest` + `coverage` | Dev/CI only |
| `ruff` | latest stable `0.x`, exact lock | Python formatting and linting in one tool | Actively maintained by Astral | Black + isort + Flake8 | Dev/CI only; replaces several heavier tools |
| `mypy` | stable 2.x | Static checking of pipeline boundaries | Mature, active project | Pyright or runtime checks only | Dev/CI only |
| Supabase CLI | `2.115.0` in offline CI and local database verification | Start the disposable local Supabase stack, apply migrations from zero, and exercise the real PostgreSQL security contract | Vendor-maintained official CLI | Hand-managed PostgreSQL/PostgREST/Auth containers | Developer/CI tool only; requires a Docker-compatible engine and never links to production |
| Wrangler | stable 4.x activation candidate; not installed | Upload one prebuilt `web/out` artifact after activation | Cloudflare-maintained official CLI | Pages REST API calls by hand | No Cloudflare upload step or credential reference exists before activation |

## Explicitly deferred

- `supabase-py`: broader than the worker's narrow REST/RPC need.
- Trafilatura/readability stacks: useful if five source-specific extractors prove too brittle, but unnecessary before fixture evidence.
- Tenacity: bounded retry and `Retry-After` logic is small and policy-specific.
- RapidFuzz, MiniSearch, Fuse.js, embeddings/vector libraries: V0.1 starts with deterministic exact/alias/keyword matching at small scale.
- Tailwind, component kits, icon packs: plain CSS and project-owned assets keep the first public bundle and design vocabulary small.
- Sentry, analytics, logging SDKs, auto-update agents: they create unapproved outbound data paths.

## Security and outbound-data effect

Installing the current packages may contact the official npm/PyPI and Playwright registries during approved bootstrap. Application and test behavior remains offline apart from localhost. The packages that would enable later application data paths are deliberately absent from the offline lockfiles:

- Live `httpx` transport, `google-genai`, and `@supabase/supabase-js` are activation-only additions.
- Wrangler is not present and the deploy workflow fails closed without reading a Cloudflare credential.
- Current collector transports are injected fixtures; browser tests contact localhost only.

No selected package adds telemetry. Lockfiles, offline network-denial tests, bundle secret scans, and dependency review on upgrades are required controls.

## Sources checked

- [npm registry: Next.js](https://registry.npmjs.org/next/latest)
- [npm registry: React](https://registry.npmjs.org/react/latest)
- [npm registry: Supabase JavaScript client](https://registry.npmjs.org/%40supabase/supabase-js/latest)
- [npm registry: Playwright](https://registry.npmjs.org/%40playwright/test/latest)
- [PyPI: Pydantic](https://pypi.org/project/pydantic/)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [uv documentation](https://docs.astral.sh/uv/)
- [Ruff documentation](https://docs.astral.sh/ruff/)
- [pytest documentation](https://docs.pytest.org/en/stable/)
- [mypy documentation](https://mypy.readthedocs.io/en/stable/)
