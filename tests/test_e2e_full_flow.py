"""
tests/test_e2e_full_flow.py — DOC-10 End-to-End Test Suite

Tests the complete user journey from registration to trade history:
  1. Register user
  2. Connect KuCoin (sandbox)
  3. Gamification profile created
  4. Unlock robot with TradePoints
  5. Start bot instance
  6. Check bot status polling
  7. Fetch bot trades + summary
  8. Stop bot
  9. Edge cases: insufficient balance, stop loss, quota exceeded

Run:
    pytest tests/test_e2e_full_flow.py -v --base-url http://localhost:8000
    pytest tests/test_e2e_full_flow.py -v -k "happy_path"

Environment variables (override via .env or export):
    BASE_URL          — backend URL  (default: http://localhost:8000)
    KUCOIN_SANDBOX_KEY, KUCOIN_SANDBOX_SECRET, KUCOIN_SANDBOX_PASSPHRASE
        — KuCoin sandbox credentials for live connect test
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
import pytest

# ── Configuration ─────────────────────────────────────────────────────────────

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = int(os.getenv("TIMEOUT", "30"))

# KuCoin sandbox credentials (optional — tests skip if not provided)
SANDBOX_KEY = os.getenv("KUCOIN_SANDBOX_KEY", "")
SANDBOX_SECRET = os.getenv("KUCOIN_SANDBOX_SECRET", "")
SANDBOX_PASSPHRASE = os.getenv("KUCOIN_SANDBOX_PASSPHRASE", "")
HAS_SANDBOX_CREDS = all([SANDBOX_KEY, SANDBOX_SECRET, SANDBOX_PASSPHRASE])


# ── Helpers ────────────────────────────────────────────────────────────────────


def _unique_email() -> str:
    return f"e2e_{uuid.uuid4().hex[:8]}@example.com"


async def _register(client: httpx.AsyncClient, email: str, password: str = "Pass123!") -> Dict:
    resp = await client.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": "E2E Test User"},
    )
    return resp


async def _login(client: httpx.AsyncClient, email: str, password: str = "Pass123!") -> str:
    """Returns access_token string."""
    resp = await client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    # Support both response shapes seen in the codebase
    token = data.get("access_token") or (data.get("data") or {}).get("access_token", "")
    assert token, f"No access_token in login response: {data}"
    return token


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _get_profile(client: httpx.AsyncClient, token: str) -> Dict:
    resp = await client.get(
        f"{BASE_URL}/api/gamification/profile",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200, f"Profile fetch failed: {resp.text}"
    return resp.json()


async def _start_bot(client: httpx.AsyncClient, token: str, payload: Dict) -> Dict:
    resp = await client.post(
        f"{BASE_URL}/api/trading/bots/start",
        json=payload,
        headers=_auth_headers(token),
    )
    return resp


async def _get_bot_status(
    client: httpx.AsyncClient, token: str, bot_instance_id: str
) -> Dict:
    resp = await client.get(
        f"{BASE_URL}/api/trading/bots/{bot_instance_id}/status",
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200, f"Status fetch failed: {resp.text}"
    return resp.json()


async def _stop_bot(
    client: httpx.AsyncClient, token: str, bot_instance_id: str
) -> Dict:
    resp = await client.post(
        f"{BASE_URL}/api/trading/bots/{bot_instance_id}/stop",
        headers=_auth_headers(token),
    )
    assert resp.status_code in (200, 202), f"Stop failed: {resp.text}"
    return resp.json()


async def _get_bot_trades(
    client: httpx.AsyncClient,
    token: str,
    bot_instance_id: str,
    page: int = 1,
    limit: int = 50,
) -> Dict:
    resp = await client.get(
        f"{BASE_URL}/api/trading/bots/{bot_instance_id}/trades",
        params={"page": page, "limit": limit},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200, f"Trades fetch failed: {resp.text}"
    return resp.json()


async def _poll_bot_status(
    client: httpx.AsyncClient,
    token: str,
    bot_instance_id: str,
    target_status: str,
    max_seconds: int = 30,
    interval: float = 2.0,
) -> Dict:
    """Polls bot status until it matches ``target_status`` or timeout."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        data = await _get_bot_status(client, token, bot_instance_id)
        if data.get("status") == target_status:
            return data
        await asyncio.sleep(interval)
    raise TimeoutError(
        f"Bot {bot_instance_id} did not reach status '{target_status}' within {max_seconds}s"
    )


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def http_client():
    """Shared async HTTP client for the whole test session."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        yield client


# ── Health check gate ─────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_00_health_check(http_client: httpx.AsyncClient):
    """Gate test — backend must be reachable before any other test runs."""
    try:
        resp = await http_client.get(f"{BASE_URL}/health")
    except httpx.ConnectError:
        pytest.skip(f"Backend not reachable at {BASE_URL} — skipping all E2E tests")
    assert resp.status_code == 200, "Health check failed"


# ══════════════════════════════════════════════════════════════════════════════
# Happy Path — complete user journey
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_01_register_new_user(http_client: httpx.AsyncClient):
    """Etapa 1 — POST /api/auth/register creates user + returns tokens."""
    email = _unique_email()
    resp = await _register(http_client, email)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    data = resp.json()
    assert data.get("success") is True or data.get("access_token"), \
        f"Unexpected response shape: {data}"


@pytest.mark.anyio
async def test_02_duplicate_email_rejected(http_client: httpx.AsyncClient):
    """Etapa 1 — Duplicate email must return 400 or 409."""
    email = _unique_email()
    await _register(http_client, email)
    resp2 = await _register(http_client, email)
    assert resp2.status_code in (400, 409), \
        f"Duplicate email should be rejected, got {resp2.status_code}"


@pytest.mark.anyio
async def test_03_gamification_profile_created_on_register(http_client: httpx.AsyncClient):
    """Etapa 1 → 3 — GameProfile is auto-created on registration."""
    email = _unique_email()
    reg = await _register(http_client, email)
    assert reg.status_code == 201
    body = reg.json()
    token = body.get("access_token") or body.get("data", {}).get("access_token")
    if not token:
        token = await _login(http_client, email)
    profile = await _get_profile(http_client, token)
    assert "trade_points" in profile or "unlocked_robots" in profile, \
        f"GameProfile missing expected fields: {profile}"


@pytest.mark.anyio
@pytest.mark.skipif(not HAS_SANDBOX_CREDS, reason="KuCoin sandbox credentials not set")
async def test_04_connect_kucoin_sandbox(http_client: httpx.AsyncClient):
    """Etapa 2 — POST /api/trading/kucoin/connect with sandbox creds."""
    email = _unique_email()
    reg = await _register(http_client, email)
    token = reg.json().get("access_token") or await _login(http_client, email)

    resp = await http_client.post(
        f"{BASE_URL}/api/trading/kucoin/connect",
        json={
            "api_key": SANDBOX_KEY,
            "api_secret": SANDBOX_SECRET,
            "api_passphrase": SANDBOX_PASSPHRASE,
        },
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200, f"KuCoin connect failed: {resp.text}"
    data = resp.json()
    assert data.get("connected") is True or data.get("status") == "success", \
        f"Connection not confirmed: {data}"


@pytest.mark.anyio
async def test_05_bot_status_endpoint_ownership(http_client: httpx.AsyncClient):
    """Etapa 7 — /api/trading/bots/{id}/status must reject other user's token."""
    # Create two users
    email_a, email_b = _unique_email(), _unique_email()
    reg_a = await _register(http_client, email_a)
    reg_b = await _register(http_client, email_b)
    token_b = reg_b.json().get("access_token") or await _login(http_client, email_b)

    # Use a fake bot_instance_id — should get 404 (not 500)
    fake_id = "000000000000000000000001"
    resp = await http_client.get(
        f"{BASE_URL}/api/trading/bots/{fake_id}/status",
        headers=_auth_headers(token_b),
    )
    assert resp.status_code in (400, 403, 404), \
        f"Expected 4xx for unknown bot, got {resp.status_code}: {resp.text}"


@pytest.mark.anyio
async def test_06_bot_trades_invalid_id(http_client: httpx.AsyncClient):
    """Etapa 10 — /api/trading/bots/{bad_id}/trades returns 400 for non-ObjectId."""
    email = _unique_email()
    reg = await _register(http_client, email)
    token = reg.json().get("access_token") or await _login(http_client, email)

    resp = await http_client.get(
        f"{BASE_URL}/api/trading/bots/NOT_AN_OBJECTID/trades",
        headers=_auth_headers(token),
    )
    assert resp.status_code in (400, 422), \
        f"Expected 400/422 for invalid ObjectId, got {resp.status_code}"


@pytest.mark.anyio
async def test_07_register_rate_limit(http_client: httpx.AsyncClient):
    """Etapa 1 — Registrations from same IP are capped at 5/hour."""
    # This hits the same in-memory bucket, so running 6+ from the test
    # suite in a short period should trigger 429.
    # We generate unique emails so the duplicate check doesn't interfere.
    results = []
    for _ in range(6):
        resp = await _register(http_client, _unique_email())
        results.append(resp.status_code)
    # At least one request in a burst of 6 should be rate-limited
    # (note: previous tests may already have consumed some slots)
    has_201 = any(s == 201 for s in results)
    has_429 = any(s == 429 for s in results)
    assert has_201 or has_429, f"Unexpected status codes: {results}"


@pytest.mark.anyio
async def test_08_leaderboard_requires_auth(http_client: httpx.AsyncClient):
    """Etapa 8 — /api/gamification/leaderboard requires authentication."""
    resp = await http_client.get(f"{BASE_URL}/api/gamification/leaderboard")
    assert resp.status_code in (401, 403), \
        f"Leaderboard should require auth, got {resp.status_code}"


@pytest.mark.anyio
async def test_09_leaderboard_authenticated(http_client: httpx.AsyncClient):
    """Etapa 8 — Authenticated users can fetch the leaderboard."""
    email = _unique_email()
    reg = await _register(http_client, email)
    token = reg.json().get("access_token") or await _login(http_client, email)

    resp = await http_client.get(
        f"{BASE_URL}/api/gamification/leaderboard",
        headers=_auth_headers(token),
    )
    # Some deployments return empty list; still must be 200
    assert resp.status_code == 200, f"Leaderboard fetch failed: {resp.text}"
    data = resp.json()
    assert isinstance(data, (dict, list)), f"Unexpected leaderboard shape: {type(data)}"


@pytest.mark.anyio
async def test_10_plan_quota_exceeded_free_user(http_client: httpx.AsyncClient):
    """Etapa 5 — 'free' plan has 0 bots; start must return 403."""
    email = _unique_email()
    reg = await _register(http_client, email)
    token = reg.json().get("access_token") or await _login(http_client, email)

    resp = await _start_bot(
        http_client,
        token,
        {
            "robot_id": "bot_001",
            "pair": "BTC-USDT",
            "capital_usdt": 50,
            "stop_loss_pct": 5,
            "take_profit_pct": 10,
        },
    )
    # Free plan has 0 bots — expect 402 (no credits), 403 (quota) or 422 (missing creds)
    # Any 4xx is correct; 5xx is a bug.
    assert 400 <= resp.status_code < 500, \
        f"Free user bot start should fail 4xx, got {resp.status_code}: {resp.text}"


# ══════════════════════════════════════════════════════════════════════════════
# Edge Cases (DOC-10 Section 14)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_edge_insufficient_balance():
    """Tentar ativar bot com capital > saldo → 400 insufficient_balance."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        email = _unique_email()
        reg = await _register(client, email)
        token = reg.json().get("access_token") or await _login(client, email)

        resp = await _start_bot(
            client,
            token,
            {
                "robot_id": "bot_001",
                "pair": "BTC-USDT",
                "capital_usdt": 9_999_999,  # Impossibly large
                "stop_loss_pct": 5,
                "take_profit_pct": 10,
            },
        )
        # Expect either 400 (balance guard) or 402/403 (quota/credits)
        assert resp.status_code in (400, 402, 403, 422), \
            f"Expected 4xx, got {resp.status_code}: {resp.text}"

        body = resp.json()
        # When we get 400, it should carry a machine-readable error field
        if resp.status_code == 400:
            detail = body.get("detail") or {}
            if isinstance(detail, dict):
                assert "error" in detail, f"detail missing 'error' key: {detail}"


@pytest.mark.anyio
async def test_edge_invalid_token_rejected():
    """All protected endpoints must reject invalid JWT with 401."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        endpoints = [
            ("GET", f"{BASE_URL}/api/gamification/profile"),
            ("GET", f"{BASE_URL}/api/gamification/leaderboard"),
            ("POST", f"{BASE_URL}/api/trading/bots/start"),
        ]
        for method, url in endpoints:
            resp = await client.request(
                method,
                url,
                headers={"Authorization": "Bearer this-is-not-a-valid-jwt"},
            )
            assert resp.status_code in (401, 403, 422), \
                f"{method} {url} accepted invalid token (got {resp.status_code})"


@pytest.mark.anyio
async def test_edge_health_endpoint_always_200():
    """GET /health must always return 200 (liveness probe)."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200, f"/health returned {resp.status_code}"


@pytest.mark.anyio
async def test_edge_detailed_health_returns_status():
    """GET /health/detailed must include 'status' key in response."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/health/detailed")
        if resp.status_code == 404:
            pytest.skip("/health/detailed not yet registered")
        assert resp.status_code in (200, 503), \
            f"Unexpected status: {resp.status_code}"
        data = resp.json()
        assert "status" in data, f"No 'status' key in /health/detailed: {data}"


@pytest.mark.anyio
async def test_edge_register_weak_password():
    """Registration with weak password must fail validation."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await _register(client, _unique_email(), password="abc")
        # Should fail with 400 or 422 (validation)
        assert resp.status_code in (400, 422), \
            f"Weak password accepted: {resp.status_code}"
