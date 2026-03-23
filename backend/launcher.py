#!/usr/bin/env python3
"""
Crypto Trade Hub Launcher
Usage:
  python launcher.py server    # Start FastAPI server
  python launcher.py worker    # Start background worker
  python launcher.py both      # Start both server and worker
"""
import asyncio
import sys
import os
import signal
from typing import Optional

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings
from app.workers.bot_worker import BotWorker

settings = get_settings()

async def start_server():
    """Start the FastAPI server"""
    print("? Starting FastAPI server...")
    os.system("python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log")

async def start_worker():
    """Start the background worker"""
    print("? Starting background worker...")
    worker = BotWorker()
    await worker.start()

async def start_both():
    """Start both server and worker"""
    print("?? Starting both FastAPI server and background worker...")

    # Start worker in background
    worker_task = asyncio.create_task(start_worker())

    # Start server (this will block)
    await start_server()

def main():
    if len(sys.argv) < 2:
        print("Usage: python launcher.py {server|worker|both}")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "server":
        # Run server directly (blocks)
        os.system("python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log")
    elif mode == "worker":
        asyncio.run(start_worker())
    elif mode == "both":
        asyncio.run(start_both())
    else:
        print(f"Invalid mode: {mode}")
        print("Usage: python launcher.py {server|worker|both}")
        sys.exit(1)

if __name__ == "__main__":
    main()
