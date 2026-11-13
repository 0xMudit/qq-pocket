"""Opt-in PostgreSQL concurrency check. Uses DATABASE_URL and synthetic records."""

import os, uuid
from concurrent.futures import ThreadPoolExecutor

assert os.environ.get("DATABASE_URL", "").startswith(
    "postgresql"
), "Requires PostgreSQL"
import app

ids = {app.submit(app.Job(task="sum", payload=[1, 2, 3]))["id"] for _ in range(8)}
with ThreadPoolExecutor(max_workers=8) as pool:
    claims = list(pool.map(lambda _: app.claim(), range(8)))
assert all(claims)
assert len({j["id"] for j in claims}) == 8
assert {j["id"] for j in claims} == ids
for job in claims:
    app.finish(job, 6)
print("PASS: eight concurrent workers acquired distinct durable jobs")
