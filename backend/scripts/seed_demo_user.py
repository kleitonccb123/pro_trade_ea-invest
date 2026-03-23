#!/usr/bin/env python
"""Script to seed a demo user into the configured MongoDB (Atlas/local).

Usage:
  python scripts/seed_demo_user.py

This script will use the application's database configuration and insert
a demo user if it does not already exist.
"""
from __future__ import annotations

import asyncio
import os
import logging

from app.core.database import connect_db, disconnect_db
from app.users.repository import UserRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo_user")


async def main():
    # Ensure offline mode is disabled for seeding
    os.environ.setdefault("OFFLINE_MODE", "false")

    await connect_db()

    demo_email = "demo@tradehub.com"
    existing = await UserRepository.find_by_email(demo_email)
    if existing:
        logger.info(f"Demo user already exists: {demo_email}")
    else:
        user = await UserRepository.create(email=demo_email, password="demo123", name="Demo User")
        logger.info(f"Created demo user: {demo_email} id={user.get('_id')}")

    await disconnect_db()


if __name__ == "__main__":
    asyncio.run(main())
