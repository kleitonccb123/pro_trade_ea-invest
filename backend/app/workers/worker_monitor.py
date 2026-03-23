# backend/app/workers/worker_monitor.py
"""
Worker Process Monitor
Monitors and restarts worker processes if they fail
"""
import asyncio
import logging
import subprocess
import sys
import os
import signal
import time
from typing import Optional

logger = logging.getLogger(__name__)

class WorkerMonitor:
    """Monitors worker processes and restarts them if they fail"""

    def __init__(self, worker_script: str = "start_worker.py", check_interval: int = 30):
        self.worker_script = worker_script
        self.check_interval = check_interval
        self.worker_process: Optional[subprocess.Popen] = None
        self.is_running = False

    async def start_monitoring(self):
        """Start monitoring the worker process"""
        logger.info("?? Starting worker process monitor")
        self.is_running = True

        while self.is_running:
            try:
                if not self._is_worker_running():
                    logger.warning("?? Worker process not found, restarting...")
                    self._start_worker()
                else:
                    logger.debug("? Worker process is running")

                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)

    def stop_monitoring(self):
        """Stop monitoring"""
        logger.info("? Stopping worker process monitor")
        self.is_running = False
        self._stop_worker()

    def _is_worker_running(self) -> bool:
        """Check if worker process is running"""
        if self.worker_process is None:
            return False

        return self.worker_process.poll() is None

    def _start_worker(self):
        """Start the worker process"""
        try:
            # Get the directory of this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            worker_path = os.path.join(script_dir, "..", self.worker_script)

            logger.info(f"? Starting worker: {worker_path}")

            # Start worker as subprocess
            self.worker_process = subprocess.Popen(
                [sys.executable, worker_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(worker_path)
            )

            logger.info(f"? Worker started with PID: {self.worker_process.pid}")

        except Exception as e:
            logger.error(f"? Failed to start worker: {e}")

    def _stop_worker(self):
        """Stop the worker process"""
        if self.worker_process and self._is_worker_running():
            try:
                logger.info("? Stopping worker process...")
                self.worker_process.terminate()

                # Wait for graceful shutdown
                try:
                    self.worker_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning("Worker didn't shutdown gracefully, forcing kill")
                    self.worker_process.kill()

                logger.info("? Worker stopped")

            except Exception as e:
                logger.error(f"Error stopping worker: {e}")

async def main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    monitor = WorkerMonitor()

    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info(f"? Received signal {signum}, stopping monitor...")
        monitor.stop_monitoring()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Monitor interrupted by user")
    except Exception as e:
        logger.error(f"Monitor failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
