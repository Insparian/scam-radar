# ADR-004: Provider-neutral AI boundary with a Gemini adapter

- **Status:** Accepted; live adapter disabled until activation
- **Date:** 2026-08-16

## Decision

Domain code depends on a provider-neutral `LLMProvider` protocol with `classify`, `extract`, `compare_patterns`, and a disabled-by-default `embed` capability. V0.1 adds one `GeminiProvider`; offline runs use recorded responses or a fake provider.

- Model IDs live only in `config/models.yaml`.
- Prompts, JSON Schemas, taxonomy, and model selection are versioned independently and included in a behavior/input hash.
- The canonical contracts are provider-neutral JSON Schema files. The Gemini adapter may translate only the supported subset.
- Validate every response again in application code. Structured output constrains shape, not factual truth or semantic correctness.
- Retry malformed output once; bound transient retries and total calls; never switch automatically to paid capacity or another model/provider.
- Send only bounded, cleaned, PII-redacted public-source text after activation. Never send reviewer notes, secrets, unrelated content, or source-page instructions as trusted instructions.
- AI proposes relevance, fields, summaries, and matches. Code decides deterministic Heat; the Evidence Gate and authenticated reviewer decide supportability and publication.
- Keep `embed()` in the interface for portability, but do not call it or store vectors until lexical failures justify a separate decision/eval.

## Why

Gemini structured output reduces parsing failures but cannot establish truth. Separating transport from contracts makes offline evals deterministic and prevents model availability or naming changes from contaminating evidence, ranking, and publishing rules.

## Alternatives

- **Gemini SDK types throughout domain code:** less adapter code, but vendor schema/model changes would ripple through evidence logic and recorded evals.
- **Raw REST only:** one fewer dependency, but duplicates official request/error handling and makes structured-output changes harder to isolate.
- **No AI:** safest but would not test the core attention-compression hypothesis; deterministic gates remain the control for AI error.

## Consequences and checks

- Schema complexity stays shallow because Gemini documents support for only a subset of JSON Schema and may reject deeply nested schemas.
- Recorded-response evals must run without a key. A manual live eval records provider/model and behavior hashes and never publishes.
- The live adapter must be impossible to call unless both the AI switch and explicit credentials are present.

## Sources

- [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini embeddings](https://ai.google.dev/gemini-api/docs/embeddings)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
