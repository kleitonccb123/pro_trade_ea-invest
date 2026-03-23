import json
import sys

url = "http://127.0.0.1:8000/api/test/create-user"
payload = {"email": "test@example.com", "password": "Test1234!", "name": "Test User"}

try:
    import httpx
    resp = httpx.post(url, json=payload, timeout=10.0)
    print(resp.status_code)
    print(resp.text)
except Exception as e:
    print("httpx failed, trying urllib. error:", e)
    try:
        from urllib import request
        data = json.dumps(payload).encode('utf-8')
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=10) as r:
            print(r.getcode())
            print(r.read().decode())
    except Exception as e2:
        print("urllib also failed:", e2)
        sys.exit(2)
