import json, time
from app import claim, finish

def run_once():
    job=claim()
    if not job: return False
    try:
        payload=json.loads(job['payload'])
        result=sum(payload) if job['task']=='sum' else payload
        finish(job,result)
    except Exception as error:
        finish(job,{"error":type(error).__name__},failed=True)
    return True

if __name__ == '__main__':
    while True:
        if not run_once(): time.sleep(0.5)
