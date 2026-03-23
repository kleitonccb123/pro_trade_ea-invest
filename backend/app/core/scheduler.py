from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable
from datetime import datetime
from bson import ObjectId

from app.core.database import get_db, get_collection
from app.bots.service import BotsService
from app.analytics.service import AnalyticsService
from app.core.config import settings
from app.notifications.service import notification_service

logger = logging.getLogger(__name__)


class Scheduler:
    """Lightweight asyncio scheduler to run background tasks inside the FastAPI process.

    - Tasks are coroutines that run in an internal loop with a given interval (seconds).
    - Scheduler can start/stop cleanly and supports multiple concurrent tasks.
    - Designed to be simple and decoupled from HTTP request handling.
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False
        # services used by tasks
        self.bots_service = BotsService()
        self.analytics_service = AnalyticsService()
        # licensing
        from app.licensing.service import licensing_service
        self.licensing = licensing_service
        # task metadata: interval, enabled flag, last_run timestamp (ISO)
        self._task_info: dict[str, dict] = {}

    async def _loop_runner(self, name: str, coro_factory: Callable[[], Awaitable[None]], interval: float):
        logger.info("Scheduler task %s starting with interval=%s", name, interval)
        try:
            while True:
                try:
                    # record start time (ISO UTC) and run
                    self._task_info.setdefault(name, {})
                    self._task_info[name]["last_run"] = datetime.utcnow().isoformat() + "Z"
                    await coro_factory()
                    # on success, set last_run to completion timestamp
                    self._task_info[name]["last_run"] = datetime.utcnow().isoformat() + "Z"
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Error in scheduled task %s", name)
                await asyncio.sleep(interval)
        finally:
            logger.info("Scheduler task %s stopped", name)

    def add_task(self, name: str, coro_factory: Callable[[], Awaitable[None]], interval: float):
        if name in self._tasks:
            raise RuntimeError(f"Task {name} already registered")
        # register metadata
        self._task_info.setdefault(name, {})
        self._task_info[name]["interval"] = interval
        self._task_info[name]["enabled"] = True
        self._task_info[name].setdefault("last_run", None)

        task = asyncio.create_task(self._loop_runner(name, coro_factory, interval))
        self._tasks[name] = task

    def get_status(self) -> dict:
        # expose a safe snapshot of scheduler state
        tasks_snapshot = {}
        for name, meta in self._task_info.items():
            tasks_snapshot[name] = {
                "enabled": bool(meta.get("enabled", False)),
                "interval": float(meta.get("interval", 0)),
            }
            if meta.get("last_run"):
                tasks_snapshot[name]["last_run"] = meta.get("last_run")

        return {
            "app_mode": settings.app_mode,
            "scheduler_running": bool(self._running),
            "tasks": tasks_snapshot,
        }

    async def start(self):
        if self._running:
            return
        self._running = True
        # register tasks according to settings
        # check licensing and settings before enabling bots
        bots_allowed = True
        try:
            bots_allowed = await self.licensing.is_feature_enabled("bots")
        except Exception:
            logger.exception("Error checking license for bots; defaulting to disabled")
            bots_allowed = False

        if settings.enable_bots and bots_allowed:
            self.add_task("bots_watch", self._ensure_bots_running, interval=settings.scheduler_bots_interval)
            logger.info("Scheduler: bots_watch enabled (interval=%s)", settings.scheduler_bots_interval)
        else:
            logger.info("Scheduler: bots_watch disabled (config=%s license=%s)", settings.enable_bots, bots_allowed)

        analytics_allowed = True
        try:
            analytics_allowed = await self.licensing.is_feature_enabled("analytics")
        except Exception:
            logger.exception("Error checking license for analytics; defaulting to disabled")
            analytics_allowed = False

        if settings.enable_analytics and analytics_allowed:
            self.add_task("analytics_recalc", self._recalc_analytics, interval=settings.scheduler_analytics_interval)
            logger.info("Scheduler: analytics_recalc enabled (interval=%s)", settings.scheduler_analytics_interval)
        else:
            logger.info("Scheduler: analytics_recalc disabled (config=%s license=%s)", settings.enable_analytics, analytics_allowed)

        # Add price alerts checker task (runs every 60 seconds)
        self.add_task("price_alerts_check", self._check_price_alerts, interval=60)
        logger.info("Scheduler: price_alerts_check enabled (interval=60s)")

        # Add strategy cleanup task (runs every 24 hours = 86400 seconds)
        self.add_task("cleanup_expired_strategies", self._cleanup_expired_strategies, interval=86400)
        logger.info("Scheduler: cleanup_expired_strategies enabled (interval=86400s / 24h)")

        # 🏆 Add leaderboard cache update task (runs every 6 hours = 21600 seconds)
        self.add_task("update_leaderboard_cache", self._update_leaderboard_cache, interval=21600)
        logger.info("Scheduler: update_leaderboard_cache enabled (interval=21600s / 6h)")

        # 📊 Add robot performance update task (runs every 4 hours = 14400 seconds)
        self.add_task("update_robot_performance", self._update_robot_performance, interval=14400)
        logger.info("Scheduler: update_robot_performance enabled (interval=14400s / 4h)")

        # 🎁 Monthly bonus: check daily (86400s) — only credits on day 1 of month
        self.add_task("monthly_bonus_check", self._monthly_bonus_check, interval=86400)
        logger.info("Scheduler: monthly_bonus_check enabled (interval=86400s / 24h, credits on day 1)")

        logger.info("Scheduler started with %s tasks", len(self._tasks))

    async def shutdown(self):
        logger.info("Scheduler shutting down %s tasks", len(self._tasks))
        for name, task in list(self._tasks.items()):
            task.cancel()
        for name, task in list(self._tasks.items()):
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Task %s cancelled", name)
            except Exception:
                logger.exception("Error while awaiting task %s", name)
        self._tasks.clear()
        self._running = False

    # --- task implementations ---
    async def _ensure_bots_running(self) -> None:
        """Ensure engine has tasks for instances marked as running in DB."""
        try:
            db = get_db()
            bot_instances = db['bot_instances']
            
            # Find all bot instances with state = 'running'
            running_instances = await bot_instances.find({'state': 'running'}).to_list(None)
            
            for inst in running_instances:
                try:
                    # instruct engine to start instance if not already
                    instance_id = inst.get('_id')
                    await self.bots_service.engine.start_instance(instance_id)
                except Exception:
                    logger.exception("Error starting instance %s", inst.get('_id'))
        except Exception:
            logger.exception("Error in _ensure_bots_running task")

    async def _recalc_analytics(self) -> None:
        """Trigger analytics recalculation (warming cache / ensuring metrics available)."""
        try:
            await self.analytics_service.summary_global()
            await self.analytics_service.pnl_timeseries()
            logger.info("Analytics recalculated")
        except Exception:
            logger.exception("Error recalculating analytics")

    async def _check_price_alerts(self) -> None:
        """Check price alerts against current market prices."""
        try:
            import httpx
            
            # Get current prices from Binance public API
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"]
            current_prices = {}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                for symbol in symbols:
                    try:
                        resp = await client.get(
                            f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            current_prices[symbol] = float(data.get("price", 0))
                    except Exception:
                        pass
            
            if current_prices:
                triggered = await notification_service.check_price_alerts(current_prices)
                if triggered:
                    logger.info(f"Price alerts triggered: {len(triggered)}")
        except Exception:
            logger.exception("Error checking price alerts")

    async def _cleanup_expired_strategies(self) -> None:
        """Clean up expired strategies (older than 6 months)."""
        try:
            db = get_db()
            strategies = db['user_strategies']
            
            # Delete strategies that have expired (expiredAt < now)
            # MongoDB automatically handles TTL indexes, but we can also manually delete
            result = await strategies.delete_many({'expires_at': {'$lt': datetime.utcnow()}})
            
            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} expired strategies")
                # Notify users about expired strategies if needed
        except Exception:
            logger.exception("Error cleaning up expired strategies")

    async def _update_leaderboard_cache(self) -> None:
        """
        🏆 Atualiza cache do leaderboard a cada 6 horas.
        
        Fluxo:
        1. Busca todos os perfis de gamificação
        2. Ordena por trade_points DESC
        3. Calcula ranks e badges
        4. Atualiza collection leaderboard_cache
        5. Log com estatísticas
        """
        try:
            from app.gamification.service import GameProfileService
            
            logger.info("🏆 Iniciando atualização do leaderboard cache...")
            
            result = await GameProfileService.update_leaderboard_cache()
            
            if result["success"]:
                logger.info(
                    f"✅ Leaderboard cache atualizado com sucesso! "
                    f"Total: {result['total_entries']} usuários"
                )
            else:
                logger.error(f"❌ Erro ao atualizar leaderboard: {result.get('error')}")
        
        except Exception:
            logger.exception("Error in _update_leaderboard_cache task")
    
    async def _update_robot_performance(self) -> None:
        """
        📊 Atualiza performance REAL de robôs a cada 4 horas.
        
        Fluxo:
        1. Busca todos os bot_instances ativos
        2. Para cada robô, calcula win_rate e profit dos últimos 15 dias
        3. Marca is_on_fire se win_rate > 60%
        4. Atualiza collection robot_rankings
        5. Log com estatísticas
        """
        try:
            from app.gamification.service import GameProfileService
            
            db = get_db()
            logger.info("📊 Iniciando atualização de performance dos robôs...")
            
            # Busca todos os bot_instances
            bot_instances = await db["bot_instances"].find().to_list(None)
            
            if not bot_instances:
                logger.info("⚠️ Nenhuma instância de bot encontrada para atualizar performance")
                return
            
            updated_count = 0
            for bot_instance in bot_instances:
                try:
                    robot_id = bot_instance.get("bot_id", "")
                    user_id = bot_instance.get("user_id", "")
                    
                    if not robot_id or not user_id:
                        continue
                    
                    # Calcula performance real (últimos 15 dias)
                    performance = await GameProfileService.calculate_robot_performance(
                        robot_id=robot_id,
                        user_id=user_id,
                        days=15
                    )
                    
                    # Atualiza robot_rankings collection
                    robot_rankings = db.get_collection("robot_rankings")
                    result = await robot_rankings.update_one(
                        {"robot_id": robot_id, "user_id": user_id},
                        {
                            "$set": {
                                "profit_24h": performance["profit_24h"],
                                "profit_7d": performance["profit_7d"],
                                "profit_15d": performance["profit_15d"],
                                "win_rate": performance["win_rate"],
                                "total_trades": performance["total_trades"],
                                "is_on_fire": performance["is_on_fire"],
                                "last_updated": datetime.utcnow(),
                            }
                        },
                        upsert=True
                    )
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao atualizar performance de {robot_id}: {str(e)}")
            
            logger.info(f"✅ Performance de {updated_count} robôs atualizada com sucesso!")
        
        except Exception:
            logger.exception("Error in _update_robot_performance task")

    async def _monthly_bonus_check(self):
        """
        🎁 Verifica se é dia 1 do mês. Se sim, credita bônus mensal.
        Roda diariamente, mas só executa no primeiro dia.
        """
        try:
            now = datetime.utcnow()
            if now.day != 1:
                logger.debug("Scheduler: monthly_bonus_check — não é dia 1, pulando")
                return
            
            from app.workers.monthly_bonus_job import credit_monthly_bonuses
            result = await credit_monthly_bonuses()
            logger.info(f"🎁 Monthly bonus job result: {result}")
        
        except Exception:
            logger.exception("Error in _monthly_bonus_check task")


# Global scheduler instance
scheduler = Scheduler()

