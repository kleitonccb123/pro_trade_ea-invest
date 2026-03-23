Backend configuration and scheduler variables

This file documents the important environment variables that control the backend automation and scheduler.

Defaults are chosen to be safe for local development.

Environment variables (place in `backend/.env`):

- `DATABASE_URL` (optional): SQLAlchemy async URL. For PostgreSQL use `postgresql+asyncpg://user:pass@localhost:5432/crypto_db`.
	If not provided the app falls back to a local SQLite file using `sqlite+aiosqlite:///./backend/dev.db` for quick local Windows development (no Docker/WSL required).
- `SECRET_KEY`: application secret for JWT (used elsewhere); keep private in production.
- `INITIAL_BALANCE` (default `10000`): simulated starting balance used by analytics.

Scheduler and automation flags:
- `ENABLE_BOTS` (default `true`): enable running automated bots engine watcher.
- `ENABLE_ANALYTICS` (default `true`): enable periodic analytics recalculation.

Scheduler intervals (seconds):
- `SCHEDULER_BOTS_INTERVAL` (default `5`)
- `SCHEDULER_ANALYTICS_INTERVAL` (default `60`)

Application mode:
- `APP_MODE` (default `dev`): application environment (dev/staging/prod). May be used to change logging or defaults.

Examples

backend/.env (development):

DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/crypto_db
SECRET_KEY=change_me_to_a_long_random_secret
INITIAL_BALANCE=10000
ENABLE_BOTS=true
ENABLE_ANALYTICS=true
SCHEDULER_BOTS_INTERVAL=5
SCHEDULER_ANALYTICS_INTERVAL=60
APP_MODE=dev

Notes
- Intervals can be lowered for faster local testing or increased in production.

Python runtime recommendation
- This backend is tested against Python 3.11. To avoid build problems (binary wheels for `asyncpg`, `cryptography`, etc.) please use Python 3.11 when installing dependencies and creating the virtualenv.

Quick setup (Windows PowerShell):

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If you cannot install Python 3.11, you will need Visual C++ Build Tools installed to compile some packages (`asyncpg`). See https://visualstudio.microsoft.com/visual-cpp-build-tools/ for the installer.
