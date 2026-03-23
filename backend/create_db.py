from __future__ import annotations

import asyncio
import os
import sys

# Ensure backend package is importable
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Use a local SQLite file inside the backend folder
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./dev.db")

from app.core.database import init_db


def main() -> None:
    asyncio.run(init_db())
    print("SQLite database created/updated at ./dev.db")


if __name__ == "__main__":
    main()
