import os
os.environ["API_KEY"]="test-secret-123456"
os.environ["DATABASE_URL"]="sqlite:///:memory:"
from fastapi.testclient import TestClient
import app
H={"x-api-key":os.environ["API_KEY"]}
def test_health():
    with TestClient(app.app) as c:
        assert c.get("/health").status_code==200
def test_queue_and_fencing():
    with TestClient(app.app) as c:
        assert c.post('/jobs',json={'task':'sum','payload':[1,2]}).status_code==401
        response=c.post('/jobs',headers=H,json={'task':'sum','payload':[1,2]})
        assert response.status_code==201
        job=app.claim()
        assert app.claim() is None
        app.finish({**job,'token':'stale'},99)
        assert c.get('/jobs',headers=H).json()[0]['status']=='running'
        app.finish(job,3)
        assert c.get('/jobs',headers=H).json()[0]['status']=='succeeded'

def test_retry_exhaustion():
    with TestClient(app.app) as c:
        c.post('/jobs',headers=H,json={'task':'echo','payload':[]})
        for attempt in range(3):
            job=app.claim(); assert job['attempts']==attempt+1
            app.finish(job,failed=True)
            with app.engine.begin() as db: db.execute(app.text("UPDATE jobs SET available=0 WHERE status='queued'"))
        assert app.claim() is None
        assert any(j['status']=='dead' for j in c.get('/jobs',headers=H).json())

import pytest
@pytest.fixture(autouse=True)
def clean_database():
    with TestClient(app.app):
        with app.engine.begin() as db:
            for table in app.SCHEMA.split(';'):
                if 'CREATE TABLE' in table:
                    table_name=table.split('EXISTS ')[1].split(' ')[0]
                    db.execute(app.text('DELETE FROM '+table_name))
    yield

def test_expired_lease_reclaimed():
    with TestClient(app.app) as c:
        c.post('/jobs',headers=H,json={'task':'sum','payload':[4,5]})
        old=app.claim()
        with app.engine.begin() as db: db.execute(app.text("UPDATE jobs SET lease=0 WHERE id=:id"),{'id':old['id']})
        new=app.claim()
        assert new['token']!=old['token'] and new['attempts']==2
        app.finish(old,100)
        app.finish(new,9)
        assert c.get('/jobs',headers=H).json()[0]['result']=='9'

def test_worker_executes_handler():
    import worker
    with TestClient(app.app) as c:
        c.post('/jobs',headers=H,json={'task':'sum','payload':[4,5]})
        assert worker.run_once()
        assert c.get('/jobs',headers=H).json()[0]['result']=='9.0'
