"""Tenant-owned durable queue and bounded worker execution."""

import hashlib
import json
import time
import uuid
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

SCHEMA = """
CREATE TABLE IF NOT EXISTS beta_jobs (id TEXT PRIMARY KEY, owner TEXT NOT NULL REFERENCES beta_users(id), idem TEXT NOT NULL, task TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, available DOUBLE PRECISION NOT NULL, created DOUBLE PRECISION NOT NULL, delay_seconds INTEGER NOT NULL DEFAULT 0, lease DOUBLE PRECISION NOT NULL DEFAULT 0, token TEXT, result TEXT, error TEXT, UNIQUE(owner,idem));
CREATE INDEX IF NOT EXISTS beta_jobs_owner ON beta_jobs(owner,created);
CREATE INDEX IF NOT EXISTS beta_jobs_ready ON beta_jobs(status,available)
"""


class Submit(BaseModel):
    task: Literal["sum", "sha256", "text_stats", "json_format"]
    payload: str = Field(max_length=20000)
    delay_seconds: int = Field(default=0, ge=0, le=86400)
    idempotency_key: str = Field(min_length=8, max_length=128)


class Acknowledge(BaseModel):
    token: str = Field(min_length=8, max_length=128)
    result: str = Field(default="", max_length=20000)
    failed: bool = False


def execute(task, payload):
    if task == "sha256":
        return hashlib.sha256(payload.encode()).hexdigest()
    if task == "text_stats":
        return {
            "characters": len(payload),
            "words": len(payload.split()),
            "lines": len(payload.splitlines()),
        }
    if task == "json_format":
        return json.dumps(
            json.loads(payload), indent=2, ensure_ascii=False, allow_nan=False
        )
    numbers = json.loads(payload)
    if (
        not isinstance(numbers, list)
        or len(numbers) > 1000
        or any(type(n) not in (int, float) for n in numbers)
    ):
        raise ValueError("sum requires a JSON array of at most 1000 numbers")
    value = sum(numbers)
    if not __import__("math").isfinite(value):
        raise ValueError("Numbers and sum must be finite")
    return value


class Product:
    def __init__(self, engine, accounts):
        self.engine = engine
        self.accounts = accounts
        self.router = APIRouter(prefix="/api", tags=["Queue"])
        self._routes()

    def initialize(self):
        with self.engine.begin() as db:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    db.execute(text(statement))

    def claim(self, owner=None):
        now = time.time()
        token = str(uuid.uuid4())
        with self.engine.begin() as db:
            db.execute(
                text(
                    "UPDATE beta_jobs SET status='dead',error='Lease expired after final attempt' WHERE status='running' AND lease<:now AND attempts>=3"
                ),
                {"now": now},
            )
            suffix = (
                " FOR UPDATE SKIP LOCKED"
                if self.engine.dialect.name == "postgresql"
                else ""
            )
            owner_clause = " AND owner=:owner" if owner else ""
            row = (
                db.execute(
                    text(
                        "SELECT * FROM beta_jobs WHERE attempts<3 AND ((status='queued' AND available<=:now) OR (status='running' AND lease<:now))"
                        + owner_clause
                        + " ORDER BY available,created LIMIT 1"
                        + suffix
                    ),
                    {"now": now, "owner": owner},
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            updated = (
                db.execute(
                    text(
                        "UPDATE beta_jobs SET status='running',attempts=attempts+1,lease=:lease,token=:token WHERE id=:id AND ((status='queued' AND available<=:now) OR (status='running' AND lease<:now)) RETURNING *"
                    ),
                    {"id": row["id"], "now": now, "lease": now + 30, "token": token},
                )
                .mappings()
                .first()
            )
            return dict(updated) if updated else None

    def finish(self, job, result=None, error=None):
        state = ("dead" if job["attempts"] >= 3 else "queued") if error else "succeeded"
        with self.engine.begin() as db:
            changed = db.execute(
                text(
                    "UPDATE beta_jobs SET status=:status,result=:result,error=:error,available=:available WHERE id=:id AND token=:token AND status='running' AND lease>:now"
                ),
                {
                    "status": state,
                    "result": (
                        json.dumps(result, ensure_ascii=False, allow_nan=False)
                        if result is not None
                        else None
                    ),
                    "error": error,
                    "available": time.time() + 2 ** job["attempts"],
                    "id": job["id"],
                    "token": job["token"],
                    "now": time.time(),
                },
            ).rowcount
        return changed == 1

    def tick(self, limit=20):
        processed = 0
        for _ in range(limit):
            job = self.claim()
            if not job:
                break
            try:
                self.finish(job, execute(job["task"], job["payload"]))
            except (ValueError, TypeError, OverflowError) as error:
                self.finish(job, error=str(error)[:500])
            processed += 1
        return {"processed": processed}

    def _routes(self):
        router = self.router
        current = self.accounts.user

        @router.get("/jobs")
        def jobs(user=Depends(current)):
            with self.engine.connect() as db:
                return [
                    dict(r)
                    for r in db.execute(
                        text(
                            "SELECT id,task,payload,status,attempts,created,available,result,error FROM beta_jobs WHERE owner=:owner ORDER BY created DESC LIMIT 200"
                        ),
                        {"owner": user["id"]},
                    ).mappings()
                ]

        @router.post("/jobs", status_code=201)
        def submit(body: Submit, background: BackgroundTasks, user=Depends(current)):
            now = time.time()
            identifier = str(uuid.uuid4())
            with self.engine.begin() as db:
                suffix = (
                    " FOR UPDATE" if self.engine.dialect.name == "postgresql" else ""
                )
                db.execute(
                    text("SELECT id FROM beta_users WHERE id=:owner" + suffix),
                    {"owner": user["id"]},
                )
                existing = (
                    db.execute(
                        text(
                            "SELECT * FROM beta_jobs WHERE owner=:owner AND idem=:key"
                        ),
                        {"owner": user["id"], "key": body.idempotency_key},
                    )
                    .mappings()
                    .first()
                )
                if existing:
                    if (
                        existing["task"] != body.task
                        or existing["payload"] != body.payload
                        or existing["delay_seconds"] != body.delay_seconds
                    ):
                        raise HTTPException(
                            409, "Idempotency key belongs to a different request"
                        )
                    return {"id": existing["id"], "status": existing["status"]}
                count = db.execute(
                    text("SELECT count(*) FROM beta_jobs WHERE owner=:owner"),
                    {"owner": user["id"]},
                ).scalar_one()
                if count >= 1000:
                    raise HTTPException(409, "Beta workspace limit: 1000 jobs")
                db.execute(
                    text(
                        "INSERT INTO beta_jobs(id,owner,idem,task,payload,status,available,created,delay_seconds) VALUES(:id,:owner,:idem,:task,:payload,'queued',:available,:created,:delay_seconds)"
                    ),
                    {
                        "id": identifier,
                        "owner": user["id"],
                        "idem": body.idempotency_key,
                        "task": body.task,
                        "payload": body.payload,
                        "available": now + body.delay_seconds,
                        "created": now,
                        "delay_seconds": body.delay_seconds,
                    },
                )
            background.add_task(self.tick, 8)
            return {"id": identifier, "status": "queued"}

        @router.post("/jobs/{identifier}/cancel")
        def cancel(identifier: str, user=Depends(current)):
            with self.engine.begin() as db:
                changed = db.execute(
                    text(
                        "UPDATE beta_jobs SET status='cancelled' WHERE id=:id AND owner=:owner AND status='queued'"
                    ),
                    {"id": identifier, "owner": user["id"]},
                ).rowcount
            if not changed:
                raise HTTPException(409, "Only your queued jobs can be cancelled")
            return {"status": "cancelled"}

        @router.post("/jobs/{identifier}/retry")
        def retry(identifier: str, background: BackgroundTasks, user=Depends(current)):
            with self.engine.begin() as db:
                changed = db.execute(
                    text(
                        "UPDATE beta_jobs SET status='queued',attempts=0,available=:now,error=NULL,result=NULL WHERE id=:id AND owner=:owner AND status IN ('dead','cancelled')"
                    ),
                    {"now": time.time(), "id": identifier, "owner": user["id"]},
                ).rowcount
            if not changed:
                raise HTTPException(409, "Only failed or cancelled jobs can be retried")
            background.add_task(self.tick, 8)
            return {"status": "queued"}

        @router.post("/worker/claim")
        def claim(user=Depends(current)):
            return self.claim(user["id"])

        @router.post("/worker/{identifier}/ack")
        def acknowledge(identifier: str, body: Acknowledge, user=Depends(current)):
            with self.engine.connect() as db:
                job = (
                    db.execute(
                        text(
                            "SELECT * FROM beta_jobs WHERE id=:id AND owner=:owner AND token=:token"
                        ),
                        {"id": identifier, "owner": user["id"], "token": body.token},
                    )
                    .mappings()
                    .first()
                )
            if not job or not self.finish(
                dict(job),
                body.result,
                "Worker reported failure" if body.failed else None,
            ):
                raise HTTPException(
                    409, "Lease is stale or job is not owned by this worker"
                )
            return {"ok": True}
