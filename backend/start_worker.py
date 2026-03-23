#!/usr/bin/env python3
"""
Bot Worker Launcher Script
Usage: python start_worker.py
"""
import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.workers.bot_worker import main

if __name__ == "__main__":
    asyncio.run(main())
