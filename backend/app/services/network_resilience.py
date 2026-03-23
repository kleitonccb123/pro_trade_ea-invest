"""
Network Resilience Utilities

Provides retry decorators with exponential backoff and circuit breaker
for handling exchange API failures gracefully.
"""
import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum

import ccxt

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"         # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit Breaker implementation for exchange API calls.

    When failure threshold is reached, circuit opens and fails fast.
    After timeout, allows limited requests to test recovery.
    """

    def __init__(
        self,
        exchange: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: tuple = (ccxt.NetworkError, ccxt.ExchangeError)
    ):
        self.exchange = exchange
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED

    @property
    def stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring."""
        return {
            "exchange": self.exchange,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "can_attempt_call": self._can_attempt_call()
        }

    def _can_attempt_call(self) -> bool:
        """Check if call can be attempted based on circuit state."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker moving to HALF_OPEN state")
                return True
            return False

        # HALF_OPEN - allow call to test recovery
        return True

    def _record_success(self):
        """Record successful call."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker closed - service recovered")

    def _record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            if self.state == CircuitBreakerState.HALF_OPEN:
                # Failed during recovery test, go back to OPEN
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            elif self.state == CircuitBreakerState.CLOSED:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
                # Trigger bot pausing when circuit opens
                asyncio.create_task(self._pause_bots_on_failure())

    async def _pause_bots_on_failure(self):
        """Pause all bots when circuit breaker opens."""
        try:
            await self._notify_and_pause_bots(self.exchange)
        except Exception as e:
            logger.error(f"Failed to pause bots on circuit breaker open: {e}")

    async def _notify_and_pause_bots(self, exchange: str):
        """Notify users and pause their bots for the failed exchange."""
        try:
            from app.core.database import get_db
            from app.services.redis_manager import redis_manager

            db = get_db()
            bot_instances_col = db['bot_instances']
            trading_sessions_col = db['trading_sessions']

            # Find all active bot instances that use this exchange
            # This is a simplified approach - in practice, you'd need to check
            # which bots are configured for which exchange
            active_bots = await bot_instances_col.find({
                'state': 'running'
            }).to_list(length=None)

            paused_bots = []
            notified_users = set()

            for bot in active_bots:
                try:
                    bot_id = bot.get('_id')
                    user_id = bot.get('user_id')  # Assuming we store user_id

                    if not user_id:
                        continue

                    # Pause the bot
                    await bot_instances_col.update_one(
                        {'_id': bot_id},
                        {
                            '$set': {
                                'state': 'paused',
                                'error_message': f'Exchange {exchange} unavailable - circuit breaker open',
                                'updated_at': datetime.utcnow()
                            }
                        }
                    )

                    paused_bots.append(str(bot_id))
                    notified_users.add(str(user_id))

                    # Broadcast notification to user's sessions
                    notification = {
                        "type": "circuit_breaker_triggered",
                        "data": {
                            "exchange": exchange,
                            "action": "bot_paused",
                            "bot_id": str(bot_id),
                            "reason": f"Exchange {exchange} failed {self.failure_threshold} times",
                            "timestamp": datetime.now().isoformat()
                        }
                    }

                    # Find user's active sessions
                    active_sessions = await trading_sessions_col.find({
                        'user_id': str(user_id),
                        'is_active': True
                    }).to_list(length=None)

                    for session in active_sessions:
                        session_id = session.get('_id')
                        if session_id:
                            await redis_manager.broadcast_to_session(
                                str(notification), session_id
                            )

                except Exception as e:
                    logger.error(f"Failed to pause bot {bot.get('_id')}: {e}")

            if paused_bots:
                logger.warning(f"Circuit breaker paused {len(paused_bots)} bots for exchange {exchange}")

        except Exception as e:
            logger.error(f"Error in _notify_and_pause_bots: {e}")

    def __call__(self, func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not self._can_attempt_call():
                raise ccxt.ExchangeError("Circuit breaker is OPEN - service unavailable")

            try:
                result = await func(*args, **kwargs)
                self._record_success()
                return result
            except self.expected_exception as e:
                self._record_failure()
                raise e

        return wrapper


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (ccxt.NetworkError, ccxt.ExchangeError, asyncio.TimeoutError)
):
    """
    Decorator that implements exponential backoff retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Factor to multiply delay by each retry
        jitter: Add random jitter to delay to prevent thundering herd
        exceptions: Tuple of exceptions to retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        # Final attempt failed
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}: {e}")
                        raise e

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)

                    if jitter:
                        # Add random jitter (?25%)
                        import random
                        jitter_amount = delay * 0.25
                        delay += random.uniform(-jitter_amount, jitter_amount)

                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            raise last_exception

        return wrapper
    return decorator


# Global circuit breakers for different exchanges
circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_all_circuit_breaker_statuses() -> Dict[str, Dict[str, Any]]:
    """Get status of all circuit breakers for monitoring."""
    return {
        exchange: circuit_breaker.stats
        for exchange, circuit_breaker in circuit_breakers.items()
    }


def resilient_ccxt_call(
    max_retries: int = 3,
    base_delay: float = 1.0,
    use_circuit_breaker: bool = True
):
    """
    Combined decorator for CCXT calls with retry and circuit breaker.

    Args:
        max_retries: Maximum retry attempts
        base_delay: Base delay for exponential backoff
        use_circuit_breaker: Whether to use circuit breaker
    """
    def decorator(func: Callable) -> Callable:
        # Apply retry decorator
        retried_func = retry_with_exponential_backoff(
            max_retries=max_retries,
            base_delay=base_delay
        )(func)

        if use_circuit_breaker:
            # Extract exchange name from function args (assuming it's a method of CCXTExchangeService)
            @wraps(retried_func)
            async def circuit_wrapper(*args, **kwargs):
                # Try to extract exchange from args (usually args[1] is exchange for classmethods)
                exchange = "unknown"
                if len(args) > 1:
                    exchange_arg = args[1]
                    if hasattr(exchange_arg, 'value'):  # Enum
                        exchange = exchange_arg.value
                    else:
                        exchange = str(exchange_arg).lower()

                circuit_breaker = get_circuit_breaker(exchange)
                protected_func = circuit_breaker(retried_func)
                return await protected_func(*args, **kwargs)

            return circuit_wrapper
        else:
            return retried_func

    return decorator


async def notify_exchange_failure(user_id: str, exchange: str, error: str):
    """
    Notify user about exchange failures and potentially pause bots.

    Args:
        user_id: User whose exchange failed
        exchange: Exchange name
        error: Error description
    """
    from app.services.redis_manager import redis_manager

    try:
        # Broadcast notification to user's sessions
        notification = {
            "type": "exchange_failure",
            "data": {
                "exchange": exchange,
                "error": error,
                "timestamp": datetime.now().isoformat(),
                "action": "bots_paused"  # Bots will be paused by circuit breaker
            }
        }

        # Find user's active sessions and broadcast
        db = None
        try:
            from app.core.database import get_db
            db = get_db()
            trading_sessions_col = db['trading_sessions']

            active_sessions = await trading_sessions_col.find({
                'user_id': str(user_id),
                'is_active': True
            }).to_list(length=None)

            for session in active_sessions:
                session_id = session.get('_id')
                if session_id:
                    await redis_manager.broadcast_to_session(
                        str(notification), session_id
                    )
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} about exchange failure: {e}")
        finally:
            if db:
                pass  # MongoDB client handles connection pooling

    except Exception as e:
        logger.error(f"Error in notify_exchange_failure: {e}")


def should_pause_bots_on_failure(exchange: str) -> bool:
    """
    Determine if bots should be paused when circuit breaker opens.

    Args:
        exchange: Exchange name

    Returns:
        True if bots should be paused
    """
    circuit_breaker = get_circuit_breaker(exchange)
    return circuit_breaker.state == CircuitBreakerState.OPEN