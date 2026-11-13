import json, time, uuid
from pydantic import BaseModel, Field, ConfigDict

TITLE = "QQ Pocket"
SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, task TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, available DOUBLE PRECISION NOT NULL, lease DOUBLE PRECISION NOT NULL DEFAULT 0, token TEXT, result TEXT); CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status, available)"""
import os, secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

database_url = os.getenv("DATABASE_URL", "sqlite:///data.db")
engine_options = {"pool_pre_ping": True}
if database_url.endswith(":memory:"):
    engine_options.update(
        connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
elif database_url.startswith("postgresql"):
    from sqlalchemy.pool import NullPool

    engine_options.update(poolclass=NullPool, connect_args={"prepare_threshold": None})
engine = create_engine(database_url, **engine_options)
if database_url.startswith("postgresql"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_schema(connection, record):
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO qq_pocket")
        connection.commit()


def auth(x_api_key: str = Header(default="")):
    if not secrets.compare_digest(x_api_key.encode(), os.environ["API_KEY"].encode()):
        raise HTTPException(401, "Invalid API key")


@asynccontextmanager
async def lifespan(app):
    if len(os.getenv("API_KEY", "")) < 16:
        raise RuntimeError("Set API_KEY to at least 16 characters")
    with engine.begin() as c:
        if engine.dialect.name == "postgresql":
            c.execute(text("CREATE SCHEMA IF NOT EXISTS qq_pocket"))
        for statement in SCHEMA.split(";"):
            if statement.strip():
                c.execute(text(statement))
    yield


app = FastAPI(title=TITLE, version="0.1.0-beta.1", lifespan=lifespan)


@app.get("/health")
def health():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ok"}


class Job(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    task: str = Field(pattern="^(echo|sum)$")
    payload: list[float] = Field(max_length=1000)


@app.post("/jobs", dependencies=[Depends(auth)], status_code=201)
def submit(job: Job):
    identifier = str(uuid.uuid4())
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO jobs(id,task,payload,status,available) VALUES(:id,:task,:payload,'queued',:now)"
            ),
            dict(
                id=identifier,
                task=job.task,
                payload=json.dumps(job.payload),
                now=time.time(),
            ),
        )
    return {"id": identifier}


@app.get("/jobs", dependencies=[Depends(auth)])
def jobs():
    with engine.connect() as c:
        return [
            dict(r)
            for r in c.execute(
                text("SELECT * FROM jobs ORDER BY available DESC LIMIT 100")
            ).mappings()
        ]


def claim():
    """Claim one eligible job; PostgreSQL locks skip competing workers."""
    now = time.time()
    token = str(uuid.uuid4())
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE jobs SET status='dead' WHERE attempts>=3 AND status='running' AND lease<:now"
            ),
            dict(now=now),
        )
        suffix = (
            " FOR UPDATE SKIP LOCKED" if engine.dialect.name == "postgresql" else ""
        )
        row = c.execute(
            text(
                "SELECT id FROM jobs WHERE attempts<3 AND ((status='queued' AND available<=:now) OR (status='running' AND lease<:now)) ORDER BY available LIMIT 1"
                + suffix
            ),
            dict(now=now),
        ).first()
        if not row:
            return None
        row = (
            c.execute(
                text(
                    "UPDATE jobs SET status='running',attempts=attempts+1,lease=:lease,token=:token WHERE id=:id AND ((status='queued' AND available<=:now) OR (status='running' AND lease<:now)) RETURNING *"
                ),
                dict(id=row.id, now=now, lease=now + 30, token=token),
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None


def finish(job, result=None, failed=False):
    """Acknowledge only the current unexpired lease owner."""
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE jobs SET status=:status,result=:result,available=:available WHERE id=:id AND token=:token AND status='running' AND lease>:now"
            ),
            dict(
                id=job["id"],
                token=job["token"],
                status=(
                    ("dead" if job["attempts"] >= 3 else "queued")
                    if failed
                    else "succeeded"
                ),
                result=json.dumps(result),
                available=time.time() + 2 ** job["attempts"],
                now=time.time(),
            ),
        )


from fastapi.responses import FileResponse
from pathlib import Path


@app.get("/")
def dashboard():
    return FileResponse(Path(__file__).with_name("demo.html"))


# Shared database rate limiting bounds the public, fixed-input demonstration.
SCHEMA += "; CREATE TABLE IF NOT EXISTS demo_limits (bucket BIGINT PRIMARY KEY, count INTEGER NOT NULL)"


def demo_budget():
    """Atomically limit public demo mutations across all API instances."""
    import time

    bucket = int(time.time() // 60)
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM demo_limits WHERE bucket < :old"), {"old": bucket - 2}
        )
        row = c.execute(
            text(
                "INSERT INTO demo_limits VALUES(:bucket,1) ON CONFLICT(bucket) DO UPDATE SET count=demo_limits.count+1 WHERE demo_limits.count<30 RETURNING count"
            ),
            {"bucket": bucket},
        ).first()
        if not row:
            raise HTTPException(429, "Demo is busy. Try again in a minute.")


@app.post("/demo/run")
def demo_run():
    """Execute a fixed synthetic scenario and return persisted evidence."""
    demo_budget()
    identifier = submit(Job(task="sum", payload=[12, 24, 36]))["id"]
    # One bounded worker tick uses the same claim and fencing implementation.
    import worker

    for _ in range(3):
        if not worker.run_once():
            break
    with engine.connect() as c:
        row = dict(
            c.execute(text("SELECT * FROM jobs WHERE id=:id"), {"id": identifier})
            .mappings()
            .one()
        )
    with engine.begin() as c:
        c.execute(
            text(
                "DELETE FROM jobs WHERE available<:old AND status IN ('succeeded','dead')"
            ),
            {"old": time.time() - 3600},
        )
    return {
        "title": (
            "Durable job processed"
            if row["status"] == "succeeded"
            else "Job persisted; processing pending"
        ),
        "checks": [
            "Job persisted before processing",
            "Atomic claim with a unique lease token",
            "Result acknowledged only by the lease owner",
        ],
        "record": row,
    }


from fastapi.staticfiles import StaticFiles

app.mount(
    "/assets", StaticFiles(directory=Path(__file__).with_name("assets")), name="assets"
)
