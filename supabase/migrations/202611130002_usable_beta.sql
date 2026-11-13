SET search_path TO qq_pocket;

CREATE TABLE IF NOT EXISTS beta_users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS beta_sessions (digest TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES beta_users(id), expires DOUBLE PRECISION NOT NULL, label TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS beta_sessions_owner ON beta_sessions(owner);
CREATE TABLE IF NOT EXISTS beta_limits (key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires DOUBLE PRECISION NOT NULL)
;

CREATE TABLE IF NOT EXISTS beta_jobs (id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES beta_users(id), idem TEXT NOT NULL, task TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, available DOUBLE PRECISION NOT NULL, created DOUBLE PRECISION NOT NULL, lease DOUBLE PRECISION NOT NULL DEFAULT 0, token TEXT, result TEXT, error TEXT, UNIQUE(owner,idem));
CREATE INDEX IF NOT EXISTS beta_jobs_owner ON beta_jobs(owner,created);
CREATE INDEX IF NOT EXISTS beta_jobs_ready ON beta_jobs(status,available)
;
