import httpx

URL = "http://127.0.0.1:8000/api/test/mock-trade"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OThiMjg3MGM0Mjg2MjU3MzZmZDMxMDUiLCJleHAiOjE3NzA3Mjg1OTF9.2VWREi5a_PXKTsc7In4C0OCmlsQpquZDAPFeZDmwXak"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

payloads = [
    {"side": "buy", "price": 48500.50, "symbol": "BTC-USDT", "amount": 0.05},
    {"side": "sell", "price": 49100.20, "symbol": "BTC-USDT", "amount": 0.05},
]

with httpx.Client(timeout=10.0) as client:
    for p in payloads:
        try:
            r = client.post(URL, json=p, headers=HEADERS)
            print('REQUEST:', p)
            print('STATUS:', r.status_code)
            print('BODY:', r.text)
        except Exception as e:
            print('ERROR:', e)
