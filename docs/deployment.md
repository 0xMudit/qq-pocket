# Deploying qq-pocket

## Runtime

The hosted beta uses Vercel FastAPI functions with Supabase PostgreSQL, TLS, and the session pooler. DATABASE_URL and the legacy operator API_KEY are Vercel secrets. The browser never receives either. Each application selects its own private schema; database-owner credentials remain shared, so least-privilege roles are future work.

## Migrations and release

1. Create a Supabase project with the CLI and link it.
2. Apply numbered SQL migrations in order. For Pocket, install pg_cron/pg_net and create the named Vault secret before applying the dispatcher migration. This dispatcher points at the public Pocket domain; change that URL for your own deployment.
3. Configure DATABASE_URL (a postgresql+psycopg URL with sslmode=require) and API_KEY (at least 16 random characters).
4. Run `python -m pytest -q` and deploy with `vercel deploy --prod`.
5. Verify `/health`, demo login, account registration, and a complete domain workflow.

Startup creates missing tables for local convenience and seeds a shared demo account. It is not a substitute for versioned ALTER migrations on an existing database. The public demo credentials are documented in README. Do not use those shared accounts for private data.

## Authentication

Registration uses a username and an Argon2 password. Browser sessions are opaque random tokens in HttpOnly/SameSite cookies; HTTPS responses set Secure. Sessions expire after seven days. API keys expire after 30 days and can be individually revoked. Private route queries constrain results by account ID. Authentication and device tokens are hashed in the database.

## Scheduled execution

Pocket uses a bounded post-response worker tick for immediate jobs. Supabase Cron checks for eligible jobs every minute and sends an authenticated request to `/internal/tick` using a secret read from Supabase Vault. That endpoint processes at most 20 jobs. The queue remains durable across failed requests; expired leases are reclaimed by later ticks. Verify cron.job_run_details and net._http_response when delayed work does not progress.

For local Pocket operation, Docker Compose runs a separate beta_worker.py process. You can also run that process against your own DATABASE_URL. Do not rely on an in-process background task alone for scheduled execution.

## Operations

Monitor errors, database connection/lock utilization, scheduler success, dead-letter volume and authentication failures. Back up PostgreSQL and test restores. Plan to add password recovery, MFA, account deletion and separate database roles before broader use. These are functional betas without an availability SLA or independently audited production-readiness claim.

The Vercel GitHub integration did not grant access to these repositories, so deployment uses the authenticated Vercel CLI. Source and test CI are on GitHub; automatic push-to-deploy is not configured.
