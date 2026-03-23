import httpx

URL = "http://127.0.0.1:8000/api/test/mock-trade"
LOGIN_URL = "http://127.0.0.1:8000/api/auth/login"

credentials = {"email": "test@example.com", "password": "Test1234!"}

payloads = [
    {"side": "buy", "price": 48500.50, "symbol": "BTC-USDT", "amount": 0.05},
    {"side": "sell", "price": 49100.20, "symbol": "BTC-USDT", "amount": 0.05},
]

def main():
    with httpx.Client(timeout=10.0) as client:
        # Login
        resp = client.post(LOGIN_URL, json=credentials)
        print('LOGIN STATUS:', resp.status_code)
        try:
            data = resp.json()
        except Exception:
            print('LOGIN BODY:', resp.text)
            raise SystemExit(2)

        token = data.get('access_token') or data.get('accessToken') or data.get('token')
        if not token:
            print('No token returned:', data)
            raise SystemExit(2)

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        for p in payloads:
            r = client.post(URL, json=p, headers=headers)
            print('REQUEST:', p)
            print('STATUS:', r.status_code)
            print('BODY:', r.text)


if __name__ == '__main__':
    main()
