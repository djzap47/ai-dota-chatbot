# Security policy

## Reporting a vulnerability

Use **Security → Report a vulnerability** on this repository if private reporting is available. If it is unavailable, open an issue asking the maintainer to arrange a private reporting channel, without including exploit details or sensitive information.

In a private report, include the affected commit, the behavior and potential impact, and minimal reproduction steps against a local test instance. Remove credentials, personal data, and database connection strings. Avoid testing the public demo in ways that consume substantial quota or change its data.

Security fixes target the current `main` branch. Older commits do not receive a separate maintenance stream.

## Operating your deployment

- Store credentials in a local `.env` or your hosting provider's environment settings. Only `.env.example` belongs in Git.
- Configure `CRON_SECRET`; maintenance endpoints are disabled when it is missing. Send it only in the authorization header.
- Apply the SQL schema or required migration before deployment. Backend tables use row-level security and deny browser-role access; the app needs a suitable backend database role.
- The public chat has a shared request budget, not individual user accounts or a monthly spending cap. Configure provider spending limits appropriate for your deployment.
- Install the pinned `requirements.txt` and review CI's dependency-audit results when updating dependencies.

See the [upgrade instructions](README.md#upgrade-an-existing-installation) and [architecture guide](docs/architecture.md) for the controls and their limits.
