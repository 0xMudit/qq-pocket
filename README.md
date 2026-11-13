# QQ Pocket

A durable background-job workspace with account-owned queues, scheduled jobs, automatic workers, and inspectable results.

[Open the beta](https://qq-pocket.vercel.app) · [API reference](https://qq-pocket.vercel.app/docs) · [Engineering lab](https://qq-pocket.vercel.app/lab) · [Issues](https://github.com/0xMudit/qq-pocket/issues)

**v0.2.0-beta.1** · FastAPI · PostgreSQL / Supabase · Vercel · MIT

## Use the application

1. Create an account or sign in to the shared demo workspace.
2. Submit a job using SHA-256, text statistics, JSON formatting, or numeric summation.
3. Schedule a delay, inspect the result, cancel queued work, or retry dead-letter jobs.
4. Create a revocable API key to submit jobs or operate a worker from another process.

### Demo credentials

Username: `demo-pocket`
Password: `PocketBeta!2026`

The demo is a shared public account. Its data and API keys are visible to others who sign in with those credentials. Create your own account for isolated data. The application is a functional beta, not a production-certified service.

## Run locally

```sh
python -m venv .venv
# Activate .venv using your shell's command.
pip install -r requirements.txt
# Set API_KEY to a random secret of at least 16 characters.
uvicorn app:app --reload
```

Open http://localhost:8000. SQLite is supported for local exploration and unit tests. Set DATABASE_URL to a PostgreSQL psycopg connection URL with TLS for deployment. On a fresh local database, startup initializes the schema and shared demo account. Hosted schema changes are provided in `supabase/migrations/`.

For Docker, copy `.env.example` to `.env`, replace its secret and run `docker compose up --build`. Change host port mappings when running multiple apps. Scheduled recovery for Pocket requires its hosted scheduler or a running beta worker; plain local API startup alone does not supply a persistent scheduler.

## API integration

Create a key in the account UI and send it as `Authorization: Bearer TOKEN`. Keys expire after 30 days and can be revoked. Browser sessions use HttpOnly cookies and expire after seven days. API payloads and validation rules are documented at `/docs`.

```text
POST /api/jobs                 Submit an idempotent job
GET  /api/jobs                  Latest 200 account-owned jobs
POST /api/jobs/{id}/cancel      Cancel queued work
POST /api/jobs/{id}/retry       Retry dead/cancelled work
POST /api/worker/claim          Claim your next eligible job
POST /api/worker/{id}/ack       Fenced acknowledgement
```

## Correctness and system design

### Queue guarantees

Submission commits before execution. A background task provides low-latency execution, while Supabase Cron invokes the protected dispatcher every minute when eligible jobs exist. The scheduler runs independently of browsers and local computers. A bounded tick processes up to 20 jobs; additional work drains on later ticks. An API worker can also claim work with a tenant API key.

Claims use PostgreSQL `FOR UPDATE SKIP LOCKED`, a 30-second lease, and an opaque token. Acknowledgement requires the current token and an unexpired lease. Three attempts are allowed; failures back off exponentially and become dead-letter jobs. A crashed worker's lease can be reclaimed. Delivery is **at least once**, not exactly once. External handlers must make their side effects idempotent.

Only four bounded built-in handlers are hosted. Arbitrary Python execution, arbitrary HTTP callbacks, and long-running jobs are not supported. Delay is up to 24 hours; the workspace holds at most 1,000 jobs. The current hosted dispatcher prioritizes oldest eligible jobs across accounts; per-tenant fairness is future work.

## Verification

```sh
python -m pytest -q
```

Tests cover ownership boundaries, session and API-key revocation, validation, and domain failure modes. `check_postgres.py` is an opt-in concurrency check for the original engineering-lab primitives; it writes synthetic data and is not a load benchmark. See [architecture](docs/architecture.md), [deployment](docs/deployment.md), and [security](SECURITY.md).

## Beta boundaries

No uptime SLA or measured throughput claim. Account usernames are not email addresses. Email verification, password recovery, MFA and self-service account deletion are not implemented. Store recoverable credentials and avoid sensitive data while evaluating the beta. Quotas and rate limits bound usage; they are not a comprehensive anti-abuse system.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Include failure-mode tests and explain concurrency assumptions in pull requests. Do not commit secrets or real location data. Licensed under MIT.

## Persistent local worker

Run `python beta_worker.py` with the same DATABASE_URL as the API, or use the included Docker Compose worker. The older `worker.py` serves the isolated engineering-lab queue.
