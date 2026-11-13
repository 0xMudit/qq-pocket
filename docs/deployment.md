# Hosted demonstration

## Topology

```mermaid
flowchart LR
  Browser --> Vercel[FastAPI on Vercel]
  Vercel --> Pool[Supabase session pooler with TLS]
  Pool --> Schema[Private qq_pocket schema]
```

## Why this design

Vercel keeps the demonstration reachable without maintaining a VM. PostgreSQL owns durable state and concurrency decisions. Supabase session pooling allows IPv4 access; SQLAlchemy NullPool avoids multiplying idle client pools across ephemeral functions. Prepared statements are disabled for pooler compatibility. Separate schemas prevent table-name collisions. They are organizational boundaries, not tenant security: these beta services currently use a shared database owner credential held only in Vercel secrets.

## Public access boundary

The browser never receives database credentials or the operator API key. Public demo actions use fixed synthetic data. A database counter limits mutations across instances to 30 per minute per application. This is a demonstration guard, not comprehensive abuse prevention. The map polling endpoint is read-only. Private schemas are not granted to Supabase anonymous/authenticated API roles.

## Scaling and feasibility

Start with one managed PostgreSQL project and three schemas: this avoids three mostly idle database instances for a portfolio demo. Every request still consumes database capacity; serverless compute scaling does not remove the database bottleneck. Observe latency, connection count, lock wait time and database CPU before increasing traffic. Load tests and measured capacity numbers remain future work.

A production evolution would use role-separated credentials, versioned migration deployment, explicit retention, structured observability, service-level objectives, and recovery drills. Those are documented tradeoffs rather than claims that this demonstration implements them.

## Deployment

1. Create and link a Supabase project with the CLI.
2. Apply `supabase/migrations/202611130001_initial.sql` to that project's database.
3. Set Vercel production secrets `DATABASE_URL` (SQLAlchemy psycopg URL with TLS) and `API_KEY`.
4. Run `vercel deploy --prod` from the repository.
5. Verify `/health`, the home page, and POST `/demo/run` without authentication.

GitHub-to-Vercel automatic linking was unavailable because the Vercel GitHub integration lacked repository access. CLI deployments work; source and CI remain on GitHub.
