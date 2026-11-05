# Changelog

## Unreleased

### Security and reliability

- Require bearer authentication for maintenance; disable these routes when no secret is configured.
- Bound chat bodies, message length, concurrent generation, provider requests, and the shared request budget.
- Return safe error responses and correct failure statuses; initialize database sessions safely across threads.
- Pin patched dependencies, remove the unused LangChain umbrella package, and add dependency auditing to CI.
- Add a migration for embedding model metadata, shared rate limits, and backend table access restrictions.

### Knowledge and chat

- Validate datasets before atomic index replacement and preserve stored text when embedding generation fails.
- Use one configured embedding model, filter incompatible vectors, enforce retrieval limits, and recover SQL transactions before fallback.
- Include item effects and named attributes; preserve curated build variants during refresh.
- Prevent overlapping browser submissions and remove duplicate curated build definitions.

### Project maintenance

- Add offline security regressions and PostgreSQL integration checks.
- Refresh the README, setup and upgrade guides, contribution guidance, and security policy.
- Expand ignore rules for environments, caches, backups, and local development artifacts.

**Upgrade:** Run [migrations/001_security.sql](migrations/001_security.sql) before deploying, install the updated requirements, then rebuild the knowledge index. See the [README](README.md#upgrade-an-existing-installation) for the sequence.
