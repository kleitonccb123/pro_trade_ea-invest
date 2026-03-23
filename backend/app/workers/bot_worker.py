# backend/app/workers/bot_worker.py
"""
Standalone Bot Worker Process
Runs trading bots independently of the FastAPI server
"""
import asyncio
import signal
import logging
import sys
from typing import Optional

from app.core.database import init_db, close_db
from app.workers.task_queue import task_queue
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class BotWorker:
    """Standalone bot worker that processes trading tasks"""

    def __init__(self):
        self.is_running = False
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """Start the bot worker"""
        logger.info("? Starting Bot Worker...")

        # Initialize database connection
        await init_db()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self.is_running = True

        try:
            # Start the task queue processor
            await task_queue.start_queue_processor()

            logger.info("? Bot Worker started successfully")
            logger.info("? Worker will process bot start/stop tasks")
            logger.info("? Press Ctrl+C to stop")

            # Wait for shutdown signal
            await self.shutdown_event.wait()

        except Exception as e:
            logger.error(f"? Bot Worker failed to start: {e}")
            raise
        finally:
            await self._shutdown()

    async def _shutdown(self):
        """Graceful shutdown"""
        logger.info("? Shutting down Bot Worker...")

        self.is_running = False

        # Stop task queue processor
        await task_queue.stop_queue_processor()

        # Close database connection
        await close_db()

        logger.info("? Bot Worker shutdown complete")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"? Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()

async def main():
    """Main entry point for the bot worker"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set offline mode for worker (no HTTP server needed)
    import os
    os.environ["OFFLINE_MODE"] = "true"

    worker = BotWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
