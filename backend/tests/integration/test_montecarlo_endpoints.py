"""
Integration Tests — Monte Carlo Simulation Endpoint  (PEND-15)
===============================================================

Tests:
  POST  /analytics/simulate/montecarlo

Covers:
  - Happy path: valid request returns P10/P50/P90 paths + summary stats
  - Low simulation count (n=100) still returns valid structure
  - Negative monthly return produces lower P50 than initial capital
  - Boundary validation: n_simulations out of range → 422
  - Boundary validation: horizon_months out of range → 422
  - Boundary validation: initial_capital ≤ 0 → 422
  - Unauthenticated request → 401/403
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from httpx import ASGITransport, AsyncClient

os.environ.setdefault("APP_MODE", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-montecarlo")
os.environ.setdefault("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "fake-secret")


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_app():
    from app.main import app
    return app


def _make_token(user_id: str = "user_mc_001") -> str:
    from jose import jwt as jose_jwt
    return jose_jwt.encode(
        {"sub": user_id, "type": "access"},
        "test-secret-montecarlo",
        algorithm="HS256",
    )


def _auth_headers(user_id: str = "user_mc_001") -> dict:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


def _mock_user(user_id: str = "user_mc_001"):
    return {
        "id": user_id,
        "email": "mc@test.com",
        "name": "MC Tester",
        "is_active": True,
        "hashed_password": "x",
        "plan": "PRO",
    }


def _mock_db_for_auth(user_id: str = "user_mc_001"):
    mock_db = MagicMock()
    mock_users = AsyncMock()
    mock_users.find_one = AsyncMock(return_value=_mock_user(user_id))
    mock_db.__getitem__ = MagicMock(return_value=mock_users)
    mock_db.users = mock_users
    return mock_db


# ── valid payload helper ──────────────────────────────────────────────────────

_VALID_PAYLOAD = {
    "initial_capital": 10000.0,
    "monthly_return_pct": 5.0,
    "annual_volatility_pct": 20.0,
    "horizon_months": 6,
    "n_simulations": 200,   # small N for speed in tests
}


# ── TestMonteCarloHappyPath ───────────────────────────────────────────────────

class TestMonteCarloHappyPath:
    """Valid requests — response structure and basic invariants."""

    @pytest.mark.asyncio
    async def test_returns_200_and_correct_structure(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json=_VALID_PAYLOAD,
                    headers=_auth_headers(),
                )

        assert resp.status_code == 200
        body = resp.json()

        # Top-level keys
        assert "paths" in body
        assert "final_p10" in body
        assert "final_p50" in body
        assert "final_p90" in body
        assert "prob_profit_pct" in body
        assert "initial_capital" in body
        assert "n_simulations" in body
        assert "horizon_months" in body

    @pytest.mark.asyncio
    async def test_paths_length_equals_horizon_plus_one(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()
        horizon = 6

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "horizon_months": horizon},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["paths"]) == horizon + 1

    @pytest.mark.asyncio
    async def test_month_zero_equals_initial_capital(self):
        """The first path point (month=0) should have P10==P50==P90==initial_capital."""
        app = _make_app()
        mock_db = _mock_db_for_auth()
        initial = 5000.0

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "initial_capital": initial},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 200
        month0 = resp.json()["paths"][0]
        assert month0["month"] == 0
        assert month0["p10"] == pytest.approx(initial, rel=1e-4)
        assert month0["p50"] == pytest.approx(initial, rel=1e-4)
        assert month0["p90"] == pytest.approx(initial, rel=1e-4)

    @pytest.mark.asyncio
    async def test_p10_lte_p50_lte_p90(self):
        """Percentile ordering: P10 ≤ P50 ≤ P90 at every month."""
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "n_simulations": 500},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 200
        for pt in resp.json()["paths"]:
            assert pt["p10"] <= pt["p50"] + 1e-6
            assert pt["p50"] <= pt["p90"] + 1e-6

    @pytest.mark.asyncio
    async def test_prob_profit_between_0_and_100(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json=_VALID_PAYLOAD,
                    headers=_auth_headers(),
                )

        body = resp.json()
        assert 0.0 <= body["prob_profit_pct"] <= 100.0

    @pytest.mark.asyncio
    async def test_negative_return_lowers_median(self):
        """With strongly negative monthly return, P50 final should be < initial_capital."""
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={
                        "initial_capital": 10000.0,
                        "monthly_return_pct": -15.0,   # strong downtrend
                        "annual_volatility_pct": 5.0,  # low vol so P50 falls predictably
                        "horizon_months": 12,
                        "n_simulations": 500,
                    },
                    headers=_auth_headers(),
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["final_p50"] < body["initial_capital"]


# ── TestMonteCarloValidation ──────────────────────────────────────────────────

class TestMonteCarloValidation:
    """Input validation: out-of-bounds values must return 422."""

    @pytest.mark.asyncio
    async def test_n_simulations_too_large(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "n_simulations": 99999},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_n_simulations_zero(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "n_simulations": 0},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_horizon_too_large(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "horizon_months": 999},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_horizon_zero(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "horizon_months": 0},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_initial_capital(self):
        app = _make_app()
        mock_db = _mock_db_for_auth()

        with patch("app.auth.router.get_db", return_value=mock_db), \
             patch("app.core.database.get_db", return_value=mock_db):

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/analytics/simulate/montecarlo",
                    json={**_VALID_PAYLOAD, "initial_capital": -100.0},
                    headers=_auth_headers(),
                )

        assert resp.status_code == 422


# ── TestMonteCarloAuth ────────────────────────────────────────────────────────

class TestMonteCarloAuth:
    """Authentication requirements."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401_or_403(self):
        app = _make_app()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/analytics/simulate/montecarlo",
                json=_VALID_PAYLOAD,
                # No Authorization header
            )

        assert resp.status_code in (401, 403)
