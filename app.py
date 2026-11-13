import json, time, uuid
from pydantic import BaseModel, Field
TITLE = "QQ Pocket"
SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, task TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, available DOUBLE PRECISION NOT NULL, lease DOUBLE PRECISION NOT NULL DEFAULT 0, token TEXT, result TEXT); CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status, available)"""
import os, secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///data.db"), **({"connect_args":{"check_same_thread":False}, "poolclass":StaticPool} if os.getenv("DATABASE_URL", "").endswith(":memory:") else {}))
def auth(x_api_key: str = Header(default="")):
    if not secrets.compare_digest(x_api_key, os.environ["API_KEY"]):
        raise HTTPException(401, "Invalid API key")
@asynccontextmanager
async def lifespan(app):
    if len(os.getenv("API_KEY", "")) < 16:
        raise RuntimeError("Set API_KEY to at least 16 characters")
    with engine.begin() as c:
        for statement in SCHEMA.split(";"):
            if statement.strip(): c.execute(text(statement))
    yield
app = FastAPI(title=TITLE, version="0.1.0-beta.1", lifespan=lifespan)
@app.get("/health")
def health():
    with engine.connect() as c: c.execute(text("SELECT 1"))
    return {"status":"ok"}

class Job(BaseModel):
    task: str = Field(pattern="^(echo|sum)$")
    payload: list[float] = Field(max_length=1000)
@app.post("/jobs", dependencies=[Depends(auth)], status_code=201)
def submit(job: Job):
    identifier = str(uuid.uuid4())
    with engine.begin() as c:
        c.execute(text("INSERT INTO jobs(id,task,payload,status,available) VALUES(:id,:task,:payload,'queued',:now)"), dict(id=identifier,task=job.task,payload=json.dumps(job.payload),now=time.time()))
    return {"id":identifier}
@app.get("/jobs", dependencies=[Depends(auth)])
def jobs():
    with engine.connect() as c: return [dict(r) for r in c.execute(text("SELECT * FROM jobs ORDER BY available DESC LIMIT 100")).mappings()]
def claim():
    now=time.time(); token=str(uuid.uuid4())
    with engine.begin() as c:
        c.execute(text("UPDATE jobs SET status='dead' WHERE attempts>=3 AND status='running' AND lease<:now"),dict(now=now))
        suffix=" FOR UPDATE SKIP LOCKED" if engine.dialect.name == "postgresql" else ""
        row=c.execute(text("SELECT id FROM jobs WHERE attempts<3 AND ((status='queued' AND available<=:now) OR (status='running' AND lease<:now)) ORDER BY available LIMIT 1"+suffix),dict(now=now)).first()
        if not row: return None
        row=c.execute(text("UPDATE jobs SET status='running',attempts=attempts+1,lease=:lease,token=:token WHERE id=:id AND ((status='queued' AND available<=:now) OR (status='running' AND lease<:now)) RETURNING *"),dict(id=row.id,now=now,lease=now+30,token=token)).mappings().first()
        return dict(row) if row else None
def finish(job, result=None, failed=False):
    with engine.begin() as c:
        c.execute(text("UPDATE jobs SET status=:status,result=:result,available=:available WHERE id=:id AND token=:token AND status='running' AND lease>:now"),dict(id=job['id'],token=job['token'],status=('dead' if job['attempts']>=3 else 'queued') if failed else 'succeeded',result=json.dumps(result),available=time.time()+2**job['attempts'],now=time.time()))
