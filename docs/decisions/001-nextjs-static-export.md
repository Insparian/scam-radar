# ADR-001: Next.js App Router with static export

- **Status:** Accepted
- **Date:** 2026-08-16

> **Amended by ADR-007:** Public content still changes only through immutable releases, but revision verification may eventually come from a narrowly activated deterministic policy path or a human exception decision. V0.1 policy outcomes remain shadow-only.

## Decision

Build `web/` with the Next.js App Router and `output: "export"`. Public pages are generated only from one local immutable release artifact. Reviewer pages are also static shells; their authenticated behavior runs in the browser.

Required configuration and boundaries:

```ts
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};
```

- `/scam/[slug]` uses `generateStaticParams()` and `dynamicParams = false`.
- No SSR, ISR, cookies, request-dependent rendering, Server Actions, rewrites, dynamic route handlers, proxy, default image optimization, or server-only authentication.
- Build-time code reads only `work/release/<release_id>/*.json`; it never fetches production data or receives a database secret.
- Public search loads the same release's local static index and never sends a query over the network.
- Browser APIs and Supabase Auth appear only in client components under the admin surface.

## Why

Public content changes only after an authorized verified revision enters an immutable release, so a rebuild is acceptable. Static output removes an always-on application server, keeps the public site available when the worker/database/AI is unhealthy, and makes it possible to publish page routes and search as one exact release.

## Alternatives

- **Full-stack Next.js on Cloudflare Workers:** Cloudflare now recommends Workers for general Next.js deployments. It is not selected because V0.1 has no request-time public use case; adding a runtime increases secret, failure, and cost surface without improving the user goal.
- **Vite/React SPA:** lighter framework, but would require us to recreate static route generation, metadata, and a useful no-JavaScript first render.
- **Runtime public Supabase reads:** would make approvals appear at different times in detail pages and search, and would expose search/network behavior unnecessarily.

## Consequences and checks

- Every public route must exist at build time; an omitted slug correctly becomes a 404.
- The admin can authenticate after hydration, but cannot depend on server redirects or cookies.
- CI rejects unsupported Next.js features, builds `web/out`, confirms all fixture slugs exist, checks one unknown slug, and scans the bundle for a sentinel secret.
- Any feature that needs request-time execution is a new architecture decision, not a small implementation shortcut.

## Official facts rechecked

Next.js 16 static export still emits an `out/` directory and explicitly does not support dynamic routes without `generateStaticParams()`, `dynamicParams: true`, cookies, ISR, default image optimization, or Server Actions. Cloudflare Pages still documents a `Next.js (Static HTML Export)` preset with `next build` and `out`, while recommending Workers for non-static Next.js use cases.

## Sources

- [Next.js static exports](https://nextjs.org/docs/app/guides/static-exports)
- [Cloudflare Pages static Next.js guide](https://developers.cloudflare.com/pages/framework-guides/nextjs/deploy-a-static-nextjs-site/)
