#!/usr/bin/env python3
"""
Worker Monitor Launcher Script
Usage: python start_monitor.py
"""
import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.workers.worker_monitor import main

if __name__ == "__main__":
    asyncio.run(main())
