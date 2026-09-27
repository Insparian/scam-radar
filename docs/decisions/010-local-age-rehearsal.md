# age for local recovery rehearsal

2026-09-18. Implements the accepted ADR-008 encryption choice for synthetic local
rehearsal only. Pin age v1.3.2; official release dated 2026-08-29 contains hardening
fixes: https://github.com/FiloSottile/age/releases/tag/v1.3.2 .

Purpose: public-recipient encryption of logical exports and isolated decryption
with a disposable synthetic recovery identity. No browser/runtime dependency.
Alternative: OpenSSL passphrase encryption is already available but would grant
routine CI decryption authority; do not substitute it for the agreed design.
Download only the official release asset, verify its GitHub-published SHA-256,
and retain executable/archive only under ignored work/. No R2 upload, production
backup, new paid service, or real recovery identity is authorized.
