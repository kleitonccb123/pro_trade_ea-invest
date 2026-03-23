"""
Resilience Layer - Circuit Breaker, Retry Logic, Rate Limiting

Implementa padr?es de resili?ncia para APIs de exchanges:
1. Circuit Breaker: Pausa chamadas ap?s falhas consecutivas
2. Retry com Backoff Exponencial: Re-tenta com delays crescentes
3. Rate Limiter: Respeita limites de requests das exchanges

Author: Crypto Trade Hub
"""

from __future__ import annotations

import asyncio
import logging
import time
import functools
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Dict, TypeVar, ParamSpec
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


# ==================== CIRCUIT BREAKER ====================

class CircuitState(str, Enum):
    """Estados do Circuit Breaker."""
    CLOSED = "closed"       # Normal - permite chamadas
    OPEN = "open"           # Aberto - bloqueia chamadas
    HALF_OPEN = "half_open" # Testando - permite uma chamada de teste


@dataclass
class CircuitBreakerConfig:
    """Configura??o do Circuit Breaker."""
    failure_threshold: int = 5          # Falhas para abrir o circuito
    success_threshold: int = 2          # Sucessos para fechar (em half-open)
    timeout: float = 60.0               # Segundos para tentar novamente
    excluded_exceptions: tuple = ()     # Exce??es que n?o contam como falha


@dataclass
class CircuitBreakerStats:
    """Estat?sticas do Circuit Breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.utcnow)
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """
    Implementa o padr?o Circuit Breaker para prote??o contra falhas em cascata.
    
    Estados:
    - CLOSED: Normal, permite todas as chamadas
    - OPEN: Ap?s X falhas, bloqueia chamadas por Y segundos
    - HALF_OPEN: Ap?s timeout, permite UMA chamada de teste
    
    Uso:
        cb = CircuitBreaker("kucoin_api")
        
        @cb
        async def call_kucoin():
            ...
    """
    
    # Registro global de circuit breakers
    _instances: Dict[str, "CircuitBreaker"] = {}
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        
        # Registrar inst?ncia
        CircuitBreaker._instances[name] = self
    
    @classmethod
    def get(cls, name: str) -> Optional["CircuitBreaker"]:
        """Obt?m um circuit breaker pelo nome."""
        return cls._instances.get(name)
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Retorna estat?sticas de todos os circuit breakers."""
        return {
            name: {
                "state": cb.stats.state.value,
                "failure_count": cb.stats.failure_count,
                "success_count": cb.stats.success_count,
                "total_calls": cb.stats.total_calls,
                "total_failures": cb.stats.total_failures,
                "last_failure": cb.stats.last_failure_time.isoformat() if cb.stats.last_failure_time else None,
            }
            for name, cb in cls._instances.items()
        }
    
    async def _check_state(self) -> bool:
        """Verifica se a chamada pode prosseguir."""
        async with self._lock:
            now = datetime.utcnow()
            
            if self.stats.state == CircuitState.CLOSED:
                return True
            
            if self.stats.state == CircuitState.OPEN:
                # Verificar se timeout passou
                time_since_failure = (now - self.stats.last_failure_time).total_seconds()
                if time_since_failure >= self.config.timeout:
                    logger.info(f"? Circuit Breaker [{self.name}]: OPEN -> HALF_OPEN (testando)")
                    self.stats.state = CircuitState.HALF_OPEN
                    self.stats.success_count = 0
                    self.stats.last_state_change = now
                    return True
                return False
            
            if self.stats.state == CircuitState.HALF_OPEN:
                return True
        
        return False
    
    async def _record_success(self):
        """Registra uma chamada bem-sucedida."""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.total_successes += 1
            
            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.success_count += 1
                if self.stats.success_count >= self.config.success_threshold:
                    logger.info(f"? Circuit Breaker [{self.name}]: HALF_OPEN -> CLOSED (recuperado)")
                    self.stats.state = CircuitState.CLOSED
                    self.stats.failure_count = 0
                    self.stats.last_state_change = datetime.utcnow()
            
            elif self.stats.state == CircuitState.CLOSED:
                # Reset failure count ap?s sucesso
                self.stats.failure_count = 0
    
    async def _record_failure(self, exception: Exception):
        """Registra uma falha."""
        async with self._lock:
            self.stats.total_calls += 1
            self.stats.total_failures += 1
            self.stats.failure_count += 1
            self.stats.last_failure_time = datetime.utcnow()
            
            if self.stats.state == CircuitState.HALF_OPEN:
                logger.warning(f"?? Circuit Breaker [{self.name}]: HALF_OPEN -> OPEN (falha no teste)")
                self.stats.state = CircuitState.OPEN
                self.stats.last_state_change = datetime.utcnow()
            
            elif self.stats.state == CircuitState.CLOSED:
                if self.stats.failure_count >= self.config.failure_threshold:
                    logger.error(
                        f"? Circuit Breaker [{self.name}]: CLOSED -> OPEN "
                        f"(threshold={self.config.failure_threshold}, timeout={self.config.timeout}s)"
                    )
                    self.stats.state = CircuitState.OPEN
                    self.stats.last_state_change = datetime.utcnow()
    
    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        """Decorator para proteger uma fun??o com circuit breaker."""
        
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Verificar se pode prosseguir
            can_proceed = await self._check_state()
            
            if not can_proceed:
                raise CircuitOpenError(
                    f"Circuit Breaker [{self.name}] est? ABERTO. "
                    f"Aguarde {self.config.timeout}s para re-tentar."
                )
            
            try:
                result = await func(*args, **kwargs)
                await self._record_success()
                return result
            
            except self.config.excluded_exceptions:
                # N?o contar como falha
                raise
            
            except Exception as e:
                await self._record_failure(e)
                raise
        
        return wrapper
    
    async def reset(self):
        """Reseta manualmente o circuit breaker."""
        async with self._lock:
            self.stats.state = CircuitState.CLOSED
            self.stats.failure_count = 0
            self.stats.success_count = 0
            self.stats.last_state_change = datetime.utcnow()
            logger.info(f"? Circuit Breaker [{self.name}]: RESET manual")


class CircuitOpenError(Exception):
    """Exce??o lan?ada quando o circuit breaker est? aberto."""
    pass


# ==================== RETRY LOGIC ====================

@dataclass
class RetryConfig:
    """Configura??o do mecanismo de retry."""
    max_attempts: int = 3                     # M?ximo de tentativas
    base_delay: float = 1.0                   # Delay inicial em segundos
    max_delay: float = 60.0                   # Delay m?ximo
    exponential_base: float = 2.0             # Base do backoff exponencial
    jitter: bool = True                       # Adicionar randomiza??o
    retryable_exceptions: tuple = (           # Exce??es que permitem retry
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )


def with_retry(config: RetryConfig = None):
    """
    Decorator para adicionar retry com backoff exponencial.
    
    Uso:
        @with_retry(RetryConfig(max_attempts=5))
        async def call_api():
            ...
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts:
                        logger.error(
                            f"? Retry [{func.__name__}]: Falhou ap?s {config.max_attempts} tentativas. "
                            f"?ltimo erro: {e}"
                        )
                        raise
                    
                    # Calcular delay com backoff exponencial
                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay
                    )
                    
                    # Adicionar jitter (0.5x a 1.5x do delay)
                    if config.jitter:
                        import random
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"?? Retry [{func.__name__}]: Tentativa {attempt}/{config.max_attempts} "
                        f"falhou ({e.__class__.__name__}). Retentando em {delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(delay)
                
                except Exception:
                    # Exce??o n?o retryable - propagar imediatamente
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator


# ==================== RATE LIMITER ====================

class RateLimiter:
    """
    Rate Limiter usando algoritmo Token Bucket.
    
    Respeita os limites de requests das exchanges:
    - KuCoin: 30 requests/segundo (p?blico), 45 (privado)
    - Binance: 1200 requests/minuto, 10 orders/segundo
    """
    
    def __init__(
        self,
        name: str,
        max_requests: int,
        time_window: float = 1.0,  # segundos
    ):
        self.name = name
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> float:
        """
        Adquire tokens. Retorna o tempo de espera (0 se imediato).
        """
        async with self._lock:
            now = time.monotonic()
            time_passed = now - self.last_update
            
            # Repor tokens
            self.tokens = min(
                self.max_requests,
                self.tokens + (time_passed / self.time_window) * self.max_requests
            )
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            
            # Calcular tempo de espera
            tokens_needed = tokens - self.tokens
            wait_time = (tokens_needed / self.max_requests) * self.time_window
            
            return wait_time
    
    async def wait_and_acquire(self, tokens: int = 1):
        """Espera e adquire tokens."""
        wait_time = await self.acquire(tokens)
        if wait_time > 0:
            logger.debug(f"? RateLimiter [{self.name}]: Aguardando {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
            await self.acquire(tokens)


def with_rate_limit(limiter: RateLimiter, tokens: int = 1):
    """Decorator para aplicar rate limiting."""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            await limiter.wait_and_acquire(tokens)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ==================== COMBINED RESILIENT CALL ====================

class ResilientExchangeClient:
    """
    Cliente resiliente para chamadas de exchange.
    
    Combina Circuit Breaker + Retry + Rate Limiter.
    """
    
    # Rate limiters por exchange
    _rate_limiters: Dict[str, RateLimiter] = {}
    
    # Circuit breakers por exchange
    _circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    @classmethod
    def get_or_create_limiter(cls, exchange: str) -> RateLimiter:
        """Obt?m ou cria rate limiter para uma exchange."""
        if exchange not in cls._rate_limiters:
            # Configura??es por exchange
            limits = {
                "kucoin": (30, 1.0),      # 30 req/s
                "binance": (20, 1.0),     # 1200/min = 20/s
                "default": (10, 1.0),
            }
            max_req, window = limits.get(exchange, limits["default"])
            cls._rate_limiters[exchange] = RateLimiter(exchange, max_req, window)
        
        return cls._rate_limiters[exchange]
    
    @classmethod
    def get_or_create_circuit_breaker(cls, exchange: str) -> CircuitBreaker:
        """Obt?m ou cria circuit breaker para uma exchange."""
        if exchange not in cls._circuit_breakers:
            config = CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30.0,
                excluded_exceptions=(ValueError, KeyError),  # Erros de valida??o n?o abrem circuito
            )
            cls._circuit_breakers[exchange] = CircuitBreaker(f"{exchange}_api", config)
        
        return cls._circuit_breakers[exchange]
    
    @classmethod
    async def call(
        cls,
        exchange: str,
        func: Callable,
        *args,
        max_retries: int = 3,
        **kwargs
    ) -> Any:
        """
        Executa uma chamada com todas as prote??es.
        
        Args:
            exchange: Nome da exchange (kucoin, binance)
            func: Fun??o async a executar
            max_retries: N?mero de tentativas
            
        Returns:
            Resultado da fun??o
            
        Raises:
            CircuitOpenError: Se o circuit breaker estiver aberto
            Exception: Ap?s esgotar retries
        """
        limiter = cls.get_or_create_limiter(exchange)
        cb = cls.get_or_create_circuit_breaker(exchange)
        
        # Rate limiting
        await limiter.wait_and_acquire()
        
        # Circuit breaker check
        can_proceed = await cb._check_state()
        if not can_proceed:
            raise CircuitOpenError(f"Circuit breaker para {exchange} est? aberto")
        
        # Retry logic
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                await cb._record_success()
                return result
            
            except (ConnectionError, TimeoutError, asyncio.TimeoutError) as e:
                last_error = e
                await cb._record_failure(e)
                
                if attempt < max_retries:
                    delay = min(2 ** attempt, 30)  # Max 30s
                    logger.warning(
                        f"?? [{exchange}] Tentativa {attempt}/{max_retries} falhou. "
                        f"Retentando em {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    await limiter.wait_and_acquire()  # Re-acquire ap?s espera
            
            except Exception as e:
                await cb._record_failure(e)
                raise
        
        raise last_error


# ==================== EXCHANGE-SPECIFIC DECORATORS ====================

# Circuit breakers pr?-configurados
kucoin_circuit = CircuitBreaker("kucoin", CircuitBreakerConfig(
    failure_threshold=5,
    timeout=60.0,
))

binance_circuit = CircuitBreaker("binance", CircuitBreakerConfig(
    failure_threshold=5,
    timeout=60.0,
))

# Rate limiters pr?-configurados
kucoin_limiter = RateLimiter("kucoin", max_requests=30, time_window=1.0)
binance_limiter = RateLimiter("binance", max_requests=20, time_window=1.0)


def resilient_kucoin_call(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator combinado para chamadas KuCoin."""
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        await kucoin_limiter.wait_and_acquire()
        return await kucoin_circuit(
            with_retry(RetryConfig(max_attempts=3))(func)
        )(*args, **kwargs)
    return wrapper


def resilient_binance_call(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator combinado para chamadas Binance."""
    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        await binance_limiter.wait_and_acquire()
        return await binance_circuit(
            with_retry(RetryConfig(max_attempts=3))(func)
        )(*args, **kwargs)
    return wrapper
