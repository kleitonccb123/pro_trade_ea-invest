"""
Engine Entry Point

Run as a standalone process:
    python -m app.engine.main

This process is completely separate from the FastAPI HTTP server.
It reads commands from the Redis queue and manages BotWorker lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

# Ensure backend/ is on the path when running as `python -m app.engine.main`
import os
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Load .env from backend/ directory (same pattern as app/main.py)
from dotenv import load_dotenv
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file)
    print(f"[OK] Engine: .env carregado de: {_env_file}")

from app.core.database import init_db, disconnect_db as close_db
from app.engine.migrations import create_indexes
from app.engine.orchestrator import BotOrchestrator, EngineCoordinator
from app.shared.redis_client import get_redis, close_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("engine.main")


async def main():
    logger.info("🔧 Inicializando Engine de Trading...")

    # Connect to database
    await init_db()
    logger.info("✅ Banco de dados conectado")

    # Create MongoDB indexes (idempotent)
    await create_indexes()
    logger.info("✅ Índices MongoDB verificados")

    # Warm up Redis connection
    redis = await get_redis()
    await redis.ping()
    logger.info("✅ Redis conectado")

    orchestrator = BotOrchestrator()

    # ── Multi-engine coordination (DOC-09) ────────────────────────────────────
    import os as _os
    engine_id = _os.getenv("ENGINE_ID", f"engine-{_os.getpid()}")
    max_bots = int(_os.getenv("MAX_BOTS_PER_ENGINE", "50"))
    coordinator = await EngineCoordinator.from_app_redis()
    logger.info(f"🔧 Engine ID: {engine_id} | Capacity: {max_bots} bots")

    # Graceful shutdown handler — works on Unix (Linux/macOS)
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(orchestrator.shutdown())
            )
    else:
        # Windows: use signal.signal fallback (less graceful)
        def _win_handler(signum, frame):
            asyncio.create_task(orchestrator.shutdown())
        signal.signal(signal.SIGINT, _win_handler)
        signal.signal(signal.SIGTERM, _win_handler)

    try:
        await asyncio.gather(
            orchestrator.start(),
            coordinator.run_heartbeat_loop(engine_id, orchestrator, max_bots),
        )
    except Exception as e:
        logger.critical(f"💥 Engine crashou de forma inesperada: {e}", exc_info=True)
        raise
    finally:
        await close_db()
        await close_redis()
        logger.info("🛑 Engine encerrada")


if __name__ == "__main__":
    asyncio.run(main())
