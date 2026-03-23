# backend/app/workers/task_queue.py
"""
Background Task Queue System for Trading Bots
Decouples bot execution from HTTP request loop
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from bson import ObjectId

from app.core.database import get_db
from app.services.strategy_engine import strategy_engine

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskType(str, Enum):
    START_BOT = "start_bot"
    STOP_BOT = "stop_bot"
    RESTART_BOT = "restart_bot"
    HEALTH_CHECK = "health_check"

@dataclass
class BackgroundTask:
    """Represents a background task"""
    task_id: str
    task_type: TaskType
    bot_id: str
    user_id: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

class TaskQueue:
    """Simple task queue using MongoDB as backend"""

    def __init__(self):
        self.collection_name = "background_tasks"
        self.active_workers: Dict[str, asyncio.Task] = {}
        self.is_running = False

    async def start_queue_processor(self):
        """Start the background task processor"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting background task queue processor")

        # Start the processor loop
        asyncio.create_task(self._process_queue_loop())

        # Start health check task
        asyncio.create_task(self._health_check_loop())

    async def stop_queue_processor(self):
        """Stop the background task processor"""
        self.is_running = False
        logger.info("Stopping background task queue processor")

        # Cancel all active workers
        for task_id, task in self.active_workers.items():
            if not task.done():
                task.cancel()

        self.active_workers.clear()

    async def enqueue_task(self, task_type: TaskType, bot_id: str, user_id: str) -> str:
        """Add a task to the queue"""
        db = get_db()

        task_id = f"{task_type.value}_{bot_id}_{datetime.utcnow().timestamp()}"

        task_data = {
            "_id": task_id,
            "task_type": task_type.value,
            "bot_id": bot_id,
            "user_id": user_id,
            "status": TaskStatus.PENDING.value,
            "created_at": datetime.utcnow(),
            "retry_count": 0,
            "max_retries": 3
        }

        await db[self.collection_name].insert_one(task_data)
        logger.info(f"? Task enqueued: {task_id} ({task_type.value})")

        return task_id

    async def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending tasks"""
        db = get_db()
        return await db[self.collection_name].find({
            "status": TaskStatus.PENDING.value
        }).sort("created_at", 1).to_list(length=None)

    async def update_task_status(self, task_id: str, status: TaskStatus,
                               error_message: Optional[str] = None):
        """Update task status"""
        db = get_db()

        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow()
        }

        if status == TaskStatus.RUNNING:
            update_data["started_at"] = datetime.utcnow()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            update_data["completed_at"] = datetime.utcnow()
            if error_message:
                update_data["error_message"] = error_message

        await db[self.collection_name].update_one(
            {"_id": task_id},
            {"$set": update_data}
        )

    async def _process_queue_loop(self):
        """Main queue processing loop"""
        while self.is_running:
            try:
                pending_tasks = await self.get_pending_tasks()

                for task_data in pending_tasks:
                    task_id = task_data["_id"]

                    # Skip if already processing
                    if task_id in self.active_workers:
                        continue

                    # Start processing task
                    worker_task = asyncio.create_task(self._process_task(task_data))
                    self.active_workers[task_id] = worker_task

                # Clean up completed workers
                completed_workers = [tid for tid, task in self.active_workers.items() if task.done()]
                for tid in completed_workers:
                    del self.active_workers[tid]

                await asyncio.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error in queue processing loop: {e}")
                await asyncio.sleep(10)

    async def _process_task(self, task_data: Dict[str, Any]):
        """Process a single task"""
        task_id = task_data["_id"]
        task_type = TaskType(task_data["task_type"])
        bot_id = task_data["bot_id"]

        try:
            logger.info(f"Processing task: {task_id} ({task_type.value})")

            # Update status to running
            await self.update_task_status(task_id, TaskStatus.RUNNING)

            # Execute the task
            if task_type == TaskType.START_BOT:
                await self._execute_start_bot(bot_id)
            elif task_type == TaskType.STOP_BOT:
                await self._execute_stop_bot(bot_id)
            elif task_type == TaskType.RESTART_BOT:
                await self._execute_restart_bot(bot_id)
            elif task_type == TaskType.HEALTH_CHECK:
                await self._execute_health_check()

            # Mark as completed
            await self.update_task_status(task_id, TaskStatus.COMPLETED)
            logger.info(f"? Task completed: {task_id}")

        except Exception as e:
            logger.error(f"? Task failed: {task_id} - {e}")

            # Update retry count
            retry_count = task_data.get("retry_count", 0) + 1
            max_retries = task_data.get("max_retries", 3)

            if retry_count < max_retries:
                # Reset to pending for retry
                await get_db()[self.collection_name].update_one(
                    {"_id": task_id},
                    {"$set": {"status": TaskStatus.PENDING.value, "retry_count": retry_count}}
                )
                logger.info(f"? Task {task_id} scheduled for retry ({retry_count}/{max_retries})")
            else:
                # Mark as failed
                await self.update_task_status(task_id, TaskStatus.FAILED, str(e))

    async def _execute_start_bot(self, bot_id: str):
        """Execute bot start task"""
        logger.info(f"? Starting bot: {bot_id}")
        await strategy_engine.start_bot_logic(bot_id)

    async def _execute_stop_bot(self, bot_id: str):
        """Execute bot stop task"""
        logger.info(f"? Stopping bot: {bot_id}")
        await strategy_engine.stop_bot_logic(bot_id)

    async def _execute_restart_bot(self, bot_id: str):
        """Execute bot restart task"""
        logger.info(f"? Restarting bot: {bot_id}")
        await strategy_engine.stop_bot_logic(bot_id)
        await asyncio.sleep(2)  # Brief pause
        await strategy_engine.start_bot_logic(bot_id)

    async def _execute_health_check(self):
        """Execute health check"""
        logger.info("? Running health check")
        # Check active bots, queue status, etc.
        active_bots = len(strategy_engine.active_tasks)
        pending_tasks = len(await self.get_pending_tasks())

        logger.info(f"? Health check: {active_bots} active bots, {pending_tasks} pending tasks")

    async def _health_check_loop(self):
        """Periodic health check"""
        while self.is_running:
            try:
                await self.enqueue_task(TaskType.HEALTH_CHECK, "system", "system")
                await asyncio.sleep(300)  # Every 5 minutes
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(60)

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        db = get_db()

        # Count tasks by status
        pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]

        status_counts = await db[self.collection_name].aggregate(pipeline).to_list(length=None)

        status_summary = {status.value: 0 for status in TaskStatus}
        for item in status_counts:
            status_summary[item["_id"]] = item["count"]

        return {
            "active_workers": len(self.active_workers),
            "is_running": self.is_running,
            "task_counts": status_summary,
            "active_bots": len(strategy_engine.active_tasks)
        }

# Global task queue instance
task_queue = TaskQueue()