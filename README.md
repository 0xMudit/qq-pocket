# Qq Pocket

Durable task queue with leased workers and bounded retries.

**0.1.0-beta.1** · Python 3.12 · FastAPI · PostgreSQL · MIT

A small, runnable backend portfolio project with explicit correctness boundaries.

## Run locally

```sh
python -m venv .venv
# Activate .venv for your shell
pip install -r requirements.txt
# Set API_KEY to a random secret of at least 16 characters
uvicorn app:app --reload
```

Local mode uses SQLite. Open http://localhost:8000/docs and supply `x-api-key` for protected operations. Health is public. For PostgreSQL, copy `.env.example` to `.env`, replace its secret, and run `docker compose up --build`. Run projects individually or change their host port mappings.

```sh
python -m pytest -q
```

## Design

See [architecture](docs/architecture.md), [operations](docs/operations.md), and [feature backlog](issues/README.md). API schemas and executable requests are available in `/docs`.

## Beta boundaries

Single trusted operator API key; no tenant isolation, public deployment hardening, measured throughput claims, or production SLA. SQLite is a development convenience. PostgreSQL concurrency must be validated before deployment. Schema bootstrap is intended for a fresh database; versioned migrations are a roadmap item.

## Contributing

Open an issue describing the behavior and reproduction. Submit focused pull requests with tests for failure modes. Never commit credentials or personal location data.

## Workers

Start the API once to initialize the schema, then run `python worker.py` in additional terminals with the same DATABASE_URL. Submit `{"task":"sum","payload":[1,2,3]}` to POST /jobs and inspect GET /jobs. Workers execute only allowlisted built-in tasks. PostgreSQL is required for concurrent deployment.

## Project planning

Track planned work in [GitHub Issues](https://github.com/0xMudit/qq-pocket/issues). This beta favors a small auditable implementation; the roadmap records what is required before broader deployment.

## Public engineering demo

The Vercel deployment uses Supabase PostgreSQL in a private `qq_pocket` schema. Open the home page and select **Run the demo**. The public endpoint accepts no arbitrary workload or financial data; it runs a fixed synthetic scenario with a database-backed limit of 30 runs per minute. Operator APIs still require a secret API key.

See [deployment and design decisions](docs/deployment.md).

**Live demo:** https://qq-pocket.vercel.app

For an opt-in database concurrency check, set DATABASE_URL to a dedicated test database with the schema applied and run `python check_postgres.py`. It writes synthetic test records.
