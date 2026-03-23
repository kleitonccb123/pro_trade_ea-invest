"""
API Monitor Service
Monitors exchange API keys and balances
Automatically disables bots if API becomes invalid or balance is low
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.error_notifier import get_notifier, AlertSeverity


class APIMonitor:
    """Monitors exchange API keys and balances for all active bots"""

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        redis: Optional[Any] = None,
        check_interval_minutes: int = 30,
        minimum_balance_usd: float = 50.0,
        max_retries: int = 3,
    ):
        """
        Initialize API monitor

        Args:
            db: MongoDB database instance
            redis: Redis instance for caching
            check_interval_minutes: How often to check (in minutes)
            minimum_balance_usd: Minimum balance in USD required
            max_retries: Max retries before disabling bot
        """
        self.db = db
        self.redis = redis
        self.check_interval_minutes = check_interval_minutes
        self.minimum_balance_usd = minimum_balance_usd
        self.max_retries = max_retries
        self.is_running = False
        self.notifier = get_notifier()

    async def start_monitoring(self) -> None:
        """Start background monitoring task"""
        if self.is_running:
            return

        self.is_running = True
        print("? API Monitor started")

        try:
            while self.is_running:
                await self._check_all_apis()
                await asyncio.sleep(self.check_interval_minutes * 60)
        except asyncio.CancelledError:
            print("API Monitor cancelled")
            self.is_running = False
        except Exception as e:
            print(f"? API Monitor error: {e}")
            self.is_running = False
            await self.notifier.notify_error(
                title="API Monitor Crashed",
                message=str(e),
                severity=AlertSeverity.CRITICAL,
                stacktrace=str(e),
            )

    async def stop_monitoring(self) -> None:
        """Stop background monitoring task"""
        self.is_running = False
        print("API Monitor stopped")

    # ========================================================================
    # Main Check Logic
    # ========================================================================

    async def _check_all_apis(self) -> None:
        """Check all active bots' APIs"""

        try:
            # Find all active bots
            active_bots = await self.db.bots.find({
                "is_active_slot": True,
                "user_id": {"$exists": True},
            }).to_list(None)

            print(f"Checking {len(active_bots)} active bots")

            for bot in active_bots:
                await self._check_bot_api(bot)

        except Exception as e:
            print(f"Error checking APIs: {e}")

    async def _check_bot_api(self, bot: Dict[str, Any]) -> None:
        """Check a single bot's API"""

        try:
            user_id = bot.get("user_id")
            bot_id = str(bot.get("_id"))
            exchange = bot.get("exchange", "unknown").lower()

            # Get user API keys
            user = await self.db.users.find_one({"_id": user_id})
            if not user:
                return

            api_keys = user.get("exchange_keys", {})
            if exchange not in api_keys:
                return

            # Check if we've already failed this bot
            fail_count = await self._get_failure_count(bot_id)

            if fail_count >= self.max_retries:
                print(f"?? Bot {bot_id} exceeded max retries, disabling")
                await self._disable_bot(bot_id, user_id, exchange)
                return

            # Validate API key
            is_valid = await self._validate_api_key(
                exchange=exchange,
                api_keys=api_keys[exchange],
            )

            if not is_valid:
                fail_count += 1
                await self._set_failure_count(bot_id, fail_count)

                # Notify on repeated failures
                if fail_count >= 3:
                    await self.notifier.notify_api_key_invalid(
                        user_id=str(user_id),
                        exchange=exchange,
                        bot_id=bot_id,
                    )

                return

            # Check balance
            balance = await self._check_balance(
                exchange=exchange,
                api_keys=api_keys[exchange],
            )

            if balance is not None and balance < self.minimum_balance_usd:
                await self.notifier.notify_api_balance_low(
                    user_id=str(user_id),
                    exchange=exchange,
                    balance=balance,
                    minimum_required=self.minimum_balance_usd,
                )

                # Auto-disable if critical low
                if balance < (self.minimum_balance_usd * 0.5):
                    print(f"? Critical low balance for bot {bot_id}")
                    await self._disable_bot(
                        bot_id,
                        user_id,
                        exchange,
                        reason="Critical low balance",
                    )
                    return

            # Reset failure count on success
            await self._set_failure_count(bot_id, 0)

        except Exception as e:
            print(f"Error checking bot API: {e}")

    # ========================================================================
    # API Validation
    # ========================================================================

    async def _validate_api_key(
        self,
        exchange: str,
        api_keys: Dict[str, str],
    ) -> bool:
        """Validate API key by making a test request"""

        try:
            if exchange == "kucoin":
                return await self._validate_kucoin_key(api_keys)
            elif exchange == "binance":
                return await self._validate_binance_key(api_keys)
            else:
                print(f"Unknown exchange: {exchange}")
                return False

        except Exception as e:
            print(f"API validation error: {e}")
            return False

    async def _validate_kucoin_key(
        self,
        api_keys: Dict[str, str],
    ) -> bool:
        """Validate KuCoin API key"""

        try:
            # Import KuCoin SDK
            from kucoin.client import Client

            client = Client(
                api_key=api_keys.get("public"),
                api_secret=api_keys.get("secret"),
                passphrase=api_keys.get("passphrase"),
            )

            # Test with simple request
            account_info = client.get_account_list()
            return bool(account_info)

        except Exception as e:
            print(f"KuCoin validation failed: {e}")
            return False

    async def _validate_binance_key(
        self,
        api_keys: Dict[str, str],
    ) -> bool:
        """Validate Binance API key"""

        try:
            # Import Binance SDK
            from binance.client import Client

            client = Client(
                api_key=api_keys.get("public"),
                api_secret=api_keys.get("secret"),
            )

            # Test with simple request
            account = client.get_account()
            return bool(account)

        except Exception as e:
            print(f"Binance validation failed: {e}")
            return False

    async def _check_balance(
        self,
        exchange: str,
        api_keys: Dict[str, str],
    ) -> Optional[float]:
        """Check account balance in USD"""

        try:
            if exchange == "kucoin":
                return await self._get_kucoin_balance(api_keys)
            elif exchange == "binance":
                return await self._get_binance_balance(api_keys)
            else:
                return None

        except Exception as e:
            print(f"Balance check error: {e}")
            return None

    async def _get_kucoin_balance(self, api_keys: Dict[str, str]) -> Optional[float]:
        """Get KuCoin account balance in USD"""

        try:
            from kucoin.client import Client

            client = Client(
                api_key=api_keys.get("public"),
                api_secret=api_keys.get("secret"),
                passphrase=api_keys.get("passphrase"),
            )

            # Get total balance
            accounts = client.get_account_list()
            total_balance = 0

            for account in accounts:
                if account.get("type") == "trade":
                    balance = float(account.get("balance", 0))
                    # Assume balance is in USD or main stablecoin
                    total_balance += balance

            return total_balance

        except Exception as e:
            print(f"KuCoin balance error: {e}")
            return None

    async def _get_binance_balance(self, api_keys: Dict[str, str]) -> Optional[float]:
        """Get Binance account balance in USD"""

        try:
            from binance.client import Client

            client = Client(
                api_key=api_keys.get("public"),
                api_secret=api_keys.get("secret"),
            )

            # Get balances
            account = client.get_account()
            total_balance = 0

            # Simplified: sum all balances (in real scenario, convert to USD)
            for balance in account.get("balances", []):
                free = Decimal(balance.get("free", 0))
                locked = Decimal(balance.get("locked", 0))
                total = free + locked

                # Simple heuristic: if asset is USDT/BUSD, add as-is
                asset = balance.get("asset", "")
                if asset in ("USDT", "BUSD", "USDC"):
                    total_balance += float(total)

            return total_balance

        except Exception as e:
            print(f"Binance balance error: {e}")
            return None

    # ========================================================================
    # Failure Tracking (Redis)
    # ========================================================================

    async def _get_failure_count(self, bot_id: str) -> int:
        """Get failure count for bot"""

        if not self.redis:
            return 0

        try:
            count = await self.redis.get(f"api_monitor:failures:{bot_id}")
            return int(count) if count else 0
        except Exception:
            return 0

    async def _set_failure_count(self, bot_id: str, count: int) -> None:
        """Set failure count for bot (expires after 24h)"""

        if not self.redis:
            return

        try:
            await self.redis.setex(
                f"api_monitor:failures:{bot_id}",
                86400,  # 24 hours
                count,
            )
        except Exception as e:
            print(f"Redis error: {e}")

    # ========================================================================
    # Bot Disabling
    # ========================================================================

    async def _disable_bot(
        self,
        bot_id: str,
        user_id: str,
        exchange: str,
        reason: str = "Invalid or expired API key",
    ) -> None:
        """Disable bot and notify user"""

        try:
            # Stop bot
            await self.db.bots.update_one(
                {"_id": bot_id},
                {
                    "$set": {
                        "is_running": False,
                        "is_active_slot": False,
                        "disabled_reason": reason,
                        "disabled_at": datetime.utcnow(),
                    }
                },
            )

            # Log event
            await self.db.audit_logs.insert_one({
                "user_id": user_id,
                "event_type": "bot_auto_disabled",
                "event_data": {
                    "bot_id": bot_id,
                    "exchange": exchange,
                    "reason": reason,
                },
                "reason": reason,
                "severity": "warning",
                "timestamp": datetime.utcnow(),
            })

            # Notify via webhook/email
            await self.notifier.notify_event(
                title="?? Bot Auto-Disabled",
                message=f"Bot was automatically disabled due to {reason}",
                severity=AlertSeverity.WARNING,
                details={
                    "user_id": str(user_id),
                    "bot_id": bot_id,
                    "exchange": exchange,
                    "reason": reason,
                },
            )

            print(f"? Bot {bot_id} disabled: {reason}")

        except Exception as e:
            print(f"Error disabling bot: {e}")


# ============================================================================
# Integration with FastAPI
# ============================================================================

async def init_api_monitor(app, db, redis=None) -> APIMonitor:
    """Initialize API monitor and add to app lifecycle"""

    monitor = APIMonitor(
        db=db,
        redis=redis,
        check_interval_minutes=30,
        minimum_balance_usd=50.0,
    )

    # Start on app startup
    @app.on_event("startup")
    async def start_monitor():
        asyncio.create_task(monitor.start_monitoring())

    # Stop on app shutdown
    @app.on_event("shutdown")
    async def stop_monitor():
        await monitor.stop_monitoring()

    return monitor
