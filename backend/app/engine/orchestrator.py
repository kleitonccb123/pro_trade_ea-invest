"""
BotOrchestrator — manages the lifecycle of all active BotWorkers.

Responsibilities:
- Listen to Redis queue for start/stop/pause/resume commands
- Spawn one asyncio.Task (BotWorker) per active bot instance
- Supervise workers with exponential-backoff retry (max 3 attempts)
- Health-check every 30 s to detect disappeared workers
- Restore running bots on process restart
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId

from app.core.database import get_db
from app.shared.redis_client import get_redis

logger = logging.getLogger("engine.orchestrator")

BOT_COMMANDS_KEY = "bot:commands"
HEALTH_CHECK_INTERVAL = 30  # seconds
MAX_WORKER_RETRIES = 3
BACKOFF_BASE = 5  # seconds  — actual waits: 5, 15, 45


class BotOrchestrator:
    """
    Central controller for the trading engine process.
    One instance runs per engine process.
    """

    def __init__(self):
        self._workers: Dict[str, object] = {}   # bot_instance_id → BotWorker
        self._tasks: Dict[str, asyncio.Task] = {}  # bot_instance_id → asyncio.Task
        self._running = False
        self._shutdown_event = asyncio.Event()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self):
        """Main entry point — runs until shutdown() is called."""
        self._running = True
        logger.info("🚀 BotOrchestrator iniciando...")

        # DOC-K09: Run startup reconciliation BEFORE restoring active bots
        try:
            from app.engine.startup_reconciler import StartupReconciler
            from app.security.cipher_singleton import get_cipher
            from app.integrations.kucoin.rest_client import KuCoinRESTClient
            import os as _os
            db = get_db()

            async def _rest_client_factory(user_id: str):
                """Creates a KuCoinRESTClient with decrypted credentials for user_id."""
                cipher    = get_cipher()
                creds_doc = await db["exchange_credentials"].find_one(
                    {"user_id": user_id, "exchange": "kucoin"}
                )
                if not creds_doc:
                    creds_doc = await db["trading_credentials"].find_one(
                        {"user_id": user_id, "is_active": True}
                    )
                if not creds_doc:
                    raise ValueError(f"Sem credenciais KuCoin para user_id={user_id}")
                if creds_doc.get("api_key_enc"):
                    dec = cipher.decrypt_credentials(
                        creds_doc["api_key_enc"],
                        creds_doc["api_secret_enc"],
                        creds_doc.get("passphrase_enc", ""),
                    )
                else:
                    dec = {
                        "api_key": creds_doc.get("api_key", ""),
                        "api_secret": creds_doc.get("api_secret", ""),
                        "passphrase": creds_doc.get("api_passphrase", ""),
                    }
                return KuCoinRESTClient(
                    api_key=dec["api_key"],
                    api_secret=dec["api_secret"],
                    api_passphrase=dec["passphrase"],
                    sandbox=_os.getenv("KUCOIN_SANDBOX", "false").lower() == "true",
                )

            reconciler = StartupReconciler(db, rest_client_factory=_rest_client_factory)
            summary = await reconciler.run()
            logger.info("[DOC-K09] Reconciliação: %s", summary)
        except Exception as rec_err:
            logger.warning("[DOC-K09] Reconciliação falhou (não crítico): %s", rec_err)

        await self._restore_active_bots()

        await asyncio.gather(
            self._command_listener(),
            self._health_monitor(),
        )

    async def shutdown(self):
        """Graceful shutdown: stop all workers, then exit the main loop."""
        logger.info("🛑 BotOrchestrator encerrando graciosamente...")
        self._running = False

        # Stop every running worker
        for bot_id in list(self._workers.keys()):
            await self._stop_worker(bot_id, reason="engine_shutdown")

        # Cancel leftover tasks
        for task in self._tasks.values():
            if not task.done():
                task.cancel()

        self._shutdown_event.set()
        logger.info("✅ Todos os workers encerrados")

    # ── Recovery ─────────────────────────────────────────────────────────────

    async def _restore_active_bots(self):
        """
        On startup, reactivate bot instances that were 'running' before a
        potential crash or restart of the engine process.
        """
        db = get_db()
        active = await db["user_bot_instances"].find(
            {"status": "running"}
        ).to_list(length=None)

        if active:
            logger.info(f"🔄 Restaurando {len(active)} robô(s) ativos do banco...")
            for inst in active:
                try:
                    inst = await self._load_decrypted_instance(db, inst)
                except Exception as cred_err:
                    logger.error(
                        f"⚠️  Credenciais não disponíveis para bot {inst['_id']} — pulando: {cred_err}"
                    )
                    continue
                await self._start_worker(str(inst["_id"]), inst)
        else:
            logger.info("ℹ️  Nenhum robô ativo para restaurar")

    # ── Command Listener ──────────────────────────────────────────────────────

    async def _command_listener(self):
        """
        Blocking-pop loop on the Redis key 'bot:commands'.
        Expected payload keys: action, bot_instance_id, [credentials]
        """
        redis = await get_redis()
        logger.info(f"👂 Aguardando comandos na fila '{BOT_COMMANDS_KEY}'...")

        while self._running:
            try:
                result = await redis.brpop(BOT_COMMANDS_KEY, timeout=5)
                if result:
                    _, raw = result
                    command = json.loads(raw)
                    await self._handle_command(command)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro no command_listener: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _handle_command(self, command: dict):
        action = command.get("action")
        bot_id = command.get("bot_instance_id")

        if action == "stop_all":
            logger.warning(f"⚠️  Comando stop_all recebido: {command.get('reason')}")
            await self.shutdown()
            return

        if not bot_id:
            logger.warning(f"Comando sem bot_instance_id: {command}")
            return

        logger.info(f"📨 Comando '{action}' para bot {bot_id}")

        if action == "start":
            db = get_db()
            inst = await db["user_bot_instances"].find_one({"_id": ObjectId(bot_id)})
            if inst:
                # DOC-K01: Decrypt credentials from DB (never pass plain-text via Redis)
                try:
                    inst = await self._load_decrypted_instance(db, inst)
                except Exception as cred_err:
                    logger.error(
                        f"❌ Falha ao descriptografar credenciais para bot {bot_id}: {cred_err}"
                    )
                    return
                await self._start_worker(bot_id, inst)
            else:
                logger.warning(f"Instância {bot_id} não encontrada no banco")

        elif action == "stop":
            await self._stop_worker(bot_id, reason=command.get("reason", "user_request"))

        elif action == "pause":
            if bot_id in self._workers:
                await self._workers[bot_id].pause()

        elif action == "resume":
            if bot_id in self._workers:
                await self._workers[bot_id].resume()

    # ── Worker Management ─────────────────────────────────────────────────────

    async def _start_worker(self, bot_id: str, instance: dict):
        if bot_id in self._workers:
            logger.warning(f"⚠️  Worker {bot_id} já está em execução — ignorando start duplicado")
            return

        # Import here to avoid circular dependency at module load time
        from app.engine.worker import BotWorker

        worker = BotWorker(instance)
        self._workers[bot_id] = worker

        task = asyncio.create_task(
            self._run_worker_with_supervision(bot_id, worker),
            name=f"bot-worker-{bot_id[:8]}",
        )
        self._tasks[bot_id] = task
        logger.info(f"✅ Worker iniciado: {bot_id}")

    async def _stop_worker(self, bot_id: str, reason: str = "unknown"):
        if bot_id not in self._workers:
            logger.warning(f"⚠️  Worker {bot_id} não encontrado para parar")
            return
        await self._workers[bot_id].stop(reason=reason)
        # Cleanup happens inside _run_worker_with_supervision's finally block

    async def _run_worker_with_supervision(self, bot_id: str, worker: object):
        """
        Runs the worker and restarts it up to MAX_WORKER_RETRIES times
        with exponential backoff on unhandled exceptions.
        A clean exit (stop() called) breaks the retry loop immediately.
        """
        retries = 0

        while retries <= MAX_WORKER_RETRIES:
            try:
                await worker.run()
                break  # Clean exit — stop() was called
            except asyncio.CancelledError:
                break
            except Exception as exc:
                retries += 1
                logger.error(
                    f"💥 Worker {bot_id} crashou "
                    f"(tentativa {retries}/{MAX_WORKER_RETRIES}): {exc}",
                    exc_info=True,
                )
                if retries > MAX_WORKER_RETRIES:
                    logger.critical(
                        f"🚨 Worker {bot_id} excedeu tentativas — marcando como erro"
                    )
                    await self._mark_bot_error(bot_id, str(exc))
                    break

                wait = BACKOFF_BASE * (3 ** (retries - 1))  # 5s, 15s, 45s
                logger.info(f"⏳ Aguardando {wait}s antes de reiniciar worker {bot_id}...")
                await asyncio.sleep(wait)

        # Cleanup
        self._workers.pop(bot_id, None)
        self._tasks.pop(bot_id, None)

    # ── Health Monitor ────────────────────────────────────────────────────────

    async def _health_monitor(self):
        """
        Every HEALTH_CHECK_INTERVAL seconds, verify that every bot instance
        marked as 'running' in the DB has a corresponding live worker.
        Restart any that have quietly disappeared.
        """
        while self._running:
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            try:
                db = get_db()
                expected = await db["user_bot_instances"].find(
                    {"status": "running"}
                ).to_list(length=None)

                for inst in expected:
                    bot_id = str(inst["_id"])
                    if bot_id not in self._workers:
                        logger.warning(
                            f"⚠️  Worker {bot_id} não encontrado — reiniciando..."
                        )
                        await self._start_worker(bot_id, inst)
            except Exception as e:
                logger.error(f"Erro no health_monitor: {e}", exc_info=True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _mark_bot_error(self, bot_id: str, error_msg: str):
        db = get_db()
        await db["user_bot_instances"].update_one(
            {"_id": ObjectId(bot_id)},
            {
                "$set": {
                    "status": "error",
                    "error_message": error_msg[:500],
                    "stopped_at": datetime.now(timezone.utc),
                }
            },
        )

    # ── DOC-K01: Credential Decryption ───────────────────────────────────────

    async def _load_decrypted_instance(self, db, instance: dict) -> dict:
        """
        DOC-K01 — Carrega credenciais criptografadas do MongoDB e injeta os
        campos decrypted_* em memória para uso pelo BotWorker.

        Os campos decrypted_* NUNCA são persistidos de volta ao banco.
        """
        try:
            from app.security.cipher_singleton import get_cipher
            from app.security.credential_encryption import CredentialEncryptionError
        except ImportError:
            logger.warning("[DOC-K01] cipher_singleton não disponível — tentando campos legados")
            return instance

        user_id = instance.get("user_id", "")

        # Procurar credenciais na coleção dedicada
        creds_doc = await db["exchange_credentials"].find_one(
            {"user_id": user_id, "exchange": "kucoin"}
        )

        # Fallback: coleção legacy trading_credentials
        if not creds_doc:
            creds_doc = await db["trading_credentials"].find_one(
                {"user_id": user_id, "is_active": True}
            )

        if not creds_doc:
            raise ValueError(
                f"[DOC-K01] Credenciais KuCoin não encontradas para user_id={user_id}"
            )

        # Se já tem campos criptografados, descriptografar via Fernet
        if creds_doc.get("api_key_enc"):
            try:
                cipher = get_cipher()
                decrypted = cipher.decrypt_credentials(
                    api_key_enc=creds_doc["api_key_enc"],
                    api_secret_enc=creds_doc["api_secret_enc"],
                    passphrase_enc=creds_doc.get("passphrase_enc", ""),
                )
                instance_copy = dict(instance)
                instance_copy["decrypted_api_key"]        = decrypted["api_key"]
                instance_copy["decrypted_api_secret"]     = decrypted["api_secret"]
                instance_copy["decrypted_api_passphrase"] = decrypted["passphrase"]
                logger.info(f"[DOC-K01] Credenciais descriptografadas para user_id={user_id}")
                return instance_copy
            except CredentialEncryptionError as e:
                raise RuntimeError(
                    f"[DOC-K01] Falha ao descriptografar credenciais para user_id={user_id}: {e}"
                ) from e

        # Fallback: campos em texto plano (legado — emitir aviso)
        if creds_doc.get("api_key"):
            logger.warning(
                f"[DOC-K01] AVISO: credenciais em texto plano para user_id={user_id} "
                "— migre para criptografia Fernet!"
            )
            instance_copy = dict(instance)
            instance_copy["decrypted_api_key"]        = creds_doc.get("api_key", "")
            instance_copy["decrypted_api_secret"]     = creds_doc.get("api_secret", "")
            instance_copy["decrypted_api_passphrase"] = creds_doc.get("api_passphrase", "")
            return instance_copy

        raise ValueError(
            f"[DOC-K01] Documento de credenciais sem campos api_key_enc ou api_key para user_id={user_id}"
        )

    def get_active_worker_count(self) -> int:
        return len(self._workers)

    def get_active_bot_ids(self) -> list:
        return list(self._workers.keys())


# ── Multi-Engine Coordinator (DOC-09) ─────────────────────────────────────────

ENGINE_REGISTRY_KEY = "engines:registry"
ENGINE_HEARTBEAT_TTL = 30  # seconds


class EngineCoordinator:
    """
    Distributes bots across multiple engine processes (horizontal scaling).

    Each engine process calls ``register_engine()`` periodically so the API
    can route start-commands to the least-loaded engine via Redis.

    Routing strategy: **least-loaded** (max free slots wins).
    Falls back to the ``"bot:commands:default"`` queue when no engines are
    registered, so single-engine deployments work without configuration.
    """

    def __init__(self, redis=None):
        self._redis = redis

    @classmethod
    async def from_app_redis(cls) -> "EngineCoordinator":
        redis = await get_redis()
        return cls(redis=redis)

    # ── Registration (called by each engine process) ──────────────────────────

    async def register_engine(
        self,
        engine_id: str,
        capacity: int,
        current_load: int,
    ) -> None:
        """
        Heartbeat: stores engine metadata in Redis hash and refreshes TTL.

        Args:
            engine_id: Unique identifier for this engine process/container.
            capacity: Maximum number of bots this engine can handle.
            current_load: Number of bots currently running on this engine.
        """
        await self._redis.hset(
            ENGINE_REGISTRY_KEY,
            engine_id,
            json.dumps(
                {
                    "capacity": capacity,
                    "current_load": current_load,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
        # Refresh TTL on the whole hash every heartbeat
        await self._redis.expire(ENGINE_REGISTRY_KEY, ENGINE_HEARTBEAT_TTL * 3)

    async def deregister_engine(self, engine_id: str) -> None:
        """Remove an engine from the registry on graceful shutdown."""
        await self._redis.hdel(ENGINE_REGISTRY_KEY, engine_id)

    # ── Routing ───────────────────────────────────────────────────────────────

    async def get_least_loaded_engine(self) -> Optional[str]:
        """
        Returns the engine_id with the most available slots, or None if the
        registry is empty (engine offline / single-process mode).
        """
        raw: Dict[bytes, bytes] = await self._redis.hgetall(ENGINE_REGISTRY_KEY)
        if not raw:
            return None

        best_engine: Optional[str] = None
        best_free_slots = -1

        for engine_id_bytes, data_bytes in raw.items():
            engine_id = (
                engine_id_bytes.decode()
                if isinstance(engine_id_bytes, bytes)
                else engine_id_bytes
            )
            try:
                data = json.loads(
                    data_bytes.decode() if isinstance(data_bytes, bytes) else data_bytes
                )
            except (json.JSONDecodeError, ValueError):
                continue

            free_slots = data.get("capacity", 0) - data.get("current_load", 0)
            if free_slots > best_free_slots:
                best_free_slots = free_slots
                best_engine = engine_id

        return best_engine

    async def get_all_engines(self) -> List[Dict]:
        """Returns a list of all registered engines with their status."""
        raw: Dict[bytes, bytes] = await self._redis.hgetall(ENGINE_REGISTRY_KEY)
        engines = []
        for engine_id_bytes, data_bytes in raw.items():
            engine_id = (
                engine_id_bytes.decode()
                if isinstance(engine_id_bytes, bytes)
                else engine_id_bytes
            )
            try:
                data = json.loads(
                    data_bytes.decode() if isinstance(data_bytes, bytes) else data_bytes
                )
            except (json.JSONDecodeError, ValueError):
                data = {}
            engines.append({"engine_id": engine_id, **data})
        return engines

    async def route_start_command(
        self, bot_instance_id: str, command: dict
    ) -> str:
        """
        Routes a bot start command to the least-loaded engine queue.

        Returns:
            The queue key used (for observability).
        """
        engine_id = await self.get_least_loaded_engine()
        if engine_id:
            queue_key = f"bot:commands:{engine_id}"
        else:
            queue_key = BOT_COMMANDS_KEY  # "bot:commands" — default / single-engine

        await self._redis.lpush(queue_key, json.dumps(command))
        return queue_key

    # ── Heartbeat loop (run inside the engine process) ────────────────────────

    async def run_heartbeat_loop(
        self,
        engine_id: str,
        orchestrator: BotOrchestrator,
        max_bots: int,
        interval: int = 10,
    ) -> None:
        """
        Infinite loop — call inside engine process alongside the orchestrator.

        Example (engine/main.py)::

            coordinator = await EngineCoordinator.from_app_redis()
            await asyncio.gather(
                orchestrator.start(),
                coordinator.run_heartbeat_loop("engine-1", orchestrator, max_bots=50),
            )
        """
        while True:
            try:
                current_load = orchestrator.get_active_worker_count()
                await self.register_engine(engine_id, max_bots, current_load)
            except Exception as exc:  # pragma: no cover
                logging.getLogger("engine.coordinator").warning(
                    f"Heartbeat falhou para {engine_id}: {exc}"
                )
            await asyncio.sleep(interval)
