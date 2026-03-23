from __future__ import annotations

import asyncio
import os
import logging
from typing import Optional
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"[OK] Arquivo .env carregado de: {env_file}")
else:
    print(f"[WARN] Arquivo .env nao encontrado em: {env_file}")

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.openapi.utils import get_openapi
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from app.core.database import init_db, connect_db, disconnect_db
from app.core.local_db_manager import init_local_db, close_local_db
# Import bots models so metadata is registered before init_db runs
import app.bots.model  # noqa: F401
import app.strategies.model  # noqa: F401
from app.core import scheduler as core_scheduler
from app.core import router as core_router
from app.core.logging_config import configure_logging
from app.core import me as me_router
from app.core.monitoring import resource_monitor  # Resource monitoring

# configure logging early using env APP_MODE
configure_logging()
logger = logging.getLogger(__name__)
from app.auth import router as auth_router
from app.auth.dependencies import get_current_user
from app.auth.two_factor_router import router as two_factor_router
from app.auth.settings_router import router as settings_router
from app.auth.license_router import router as license_router
from app.auth.forgot_password_router import router as forgot_password_router
from app.auth.lgpd_router import router as lgpd_router
from app.bots import router as bots_router
from app.bots.execution_router import router as execution_router
from app.analytics import router as analytics_router
from app.trading import router as trading_router
from app.trading.audit_router import router as audit_router
from app.trading.validation_router import router as validation_router
from app.trading.kill_switch_router import router as kill_switch_router
from app.notifications import router as notifications_router
from app.strategies import router as strategies_router
from app.affiliates import router as affiliates_router
from app.education import router as education_router
from app.chat import router as chat_router
from app.websockets.notification_router import router as ws_notifications_router
from app.gamification import router as gamification_router
import app.notifications.models  # noqa: F401 - Register notification models
from app.services.redis_manager import redis_manager
from app.real_time import test_realtime_router
from app.workers.task_queue import task_queue
from app.middleware.csp import GoogleOAuthCSPMiddleware
from app.middleware.csrf import CSRFMiddleware
from app.routers.billing import router as billing_router
from app.strategy_manager import router as strategy_manager_router
from app.services.strategy_manager import recover_all_users_on_startup
from app.ea_monitor.router import router as ea_monitor_router, ws_router as ea_monitor_ws_router
from app.marketplace.robots_router import router as marketplace_robots_router


# ============================================
# ? Swagger/OpenAPI Configuration
# ============================================

API_TITLE = "Crypto Trade Hub API"
API_VERSION = "2.0.0"
API_DESCRIPTION = """
# ? Crypto Trade Hub - Trading Automation Platform

API completa para automa??o de trading de criptomoedas com rob?s inteligentes.

## ? Autentica??o

Todos os endpoints (exceto `/health` e `/auth/*`) requerem autentica??o via **Bearer Token**.

```
Authorization: Bearer <seu_token_jwt>
```

Obtenha o token via `POST /auth/login`.

## ? Categorias de Endpoints

| Tag | Descri??o |
|-----|-----------|
| ? **Auth** | Autentica??o, registro e 2FA |
| ? **Users** | Perfil e configura??es do usu?rio |
| ? **Bots** | Criar, gerenciar e monitorar rob?s de trading |
| ? **Trading** | Opera??es de trading e valida??es |
| ? **Analytics** | Estat?sticas e relat?rios de performance |
| ? **Strategies** | Estrat?gias de trading personalizadas |
| ? **Notifications** | Sistema de notifica??es em tempo real |
| ? **Education** | M?dulos educacionais e v?deos |
| ? **Affiliates** | Sistema de afiliados e comiss?es |
| ?? **Admin** | Fun??es administrativas e emerg?ncia |

## ?? Rate Limits

- **Autentica??o**: 5 requests/minuto por IP
- **Trading**: 60 requests/minuto por usu?rio
- **Consultas**: 120 requests/minuto por usu?rio

## ? Suporte

- ? Email: suporte@cryptotradehub.com
- ? Docs: https://docs.cryptotradehub.com
"""

# Tags para organiza??o do Swagger
OPENAPI_TAGS = [
    {
        "name": "? Auth",
        "description": "Autentica??o e gerenciamento de sess?es. Inclui login, registro, logout, refresh token e 2FA.",
    },
    {
        "name": "? Users",
        "description": "Gerenciamento de perfil do usu?rio, configura??es pessoais e prefer?ncias.",
    },
    {
        "name": "? Bots",
        "description": """
Gerenciamento de rob?s de trading automatizado.

**Opera??es principais:**
- Criar novos rob?s com diferentes estrat?gias
- Iniciar/parar execu??o
- Monitorar performance em tempo real
- Configurar par?metros de risco
        """,
    },
    {
        "name": "? Trading",
        "description": """
Opera??es de trading e valida??o de ordens.

**Inclui:**
- Valida??o pr?-trade (limites, precis?o)
- Auditoria de opera??es
- Hist?rico de P&L
        """,
    },
    {
        "name": "? Analytics",
        "description": "Estat?sticas, m?tricas de performance, relat?rios de lucro/preju?zo e an?lises de mercado.",
    },
    {
        "name": "? Strategies",
        "description": """
Estrat?gias de trading configur?veis.

**Estrat?gias dispon?veis:**
- Grid Trading
- DCA (Dollar Cost Averaging)
- Scalping
- Custom (personalizada)
        """,
    },
    {
        "name": "? Notifications",
        "description": "Sistema de notifica??es push, webhooks e alertas em tempo real via WebSocket.",
    },
    {
        "name": "? Education",
        "description": "M?dulos educacionais, v?deos tutoriais, cursos e certifica??es de trading.",
    },
    {
        "name": "? Affiliates",
        "description": "Sistema de afiliados, links de refer?ncia, comiss?es e relat?rios de ganhos.",
    },
    {
        "name": "?? Admin",
        "description": """
**?? FUN??ES ADMINISTRATIVAS E EMERG?NCIA**

Endpoints cr?ticos para administra??o do sistema:
- **Kill Switch**: Parada de emerg?ncia de todos os rob?s
- **Licenciamento**: Gerenciamento de licen?as de usu?rios
- **Monitoramento**: Health checks e m?tricas do sistema
        """,
    },
    {
        "name": "?? Health",
        "description": "Endpoints de health check para monitoramento e load balancers.",
    },
]


def custom_openapi():
    """Gera schema OpenAPI customizado com metadados ricos."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    
    # Adicionar informa??es de contato e licen?a
    openapi_schema["info"]["contact"] = {
        "name": "Crypto Trade Hub Support",
        "url": "https://cryptotradehub.com/support",
        "email": "api@cryptotradehub.com",
    }
    
    openapi_schema["info"]["license"] = {
        "name": "Proprietary",
        "url": "https://cryptotradehub.com/terms",
    }
    
    # Adicionar servidores
    openapi_schema["servers"] = [
        {"url": "/", "description": "Servidor atual"},
        {"url": "http://localhost:8000", "description": "Desenvolvimento local"},
    ]
    
    # Adicionar esquema de seguran?a
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token JWT obtido via POST /auth/login",
        }
    }
    
    # Aplicar seguran?a global (exceto endpoints p?blicos)
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


_is_prod = os.getenv("APP_MODE", "dev") == "prod"
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters={
        "docExpansion": "none",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "syntaxHighlight.theme": "monokai",
    },
)

# Aplicar schema customizado
app.openapi = custom_openapi

# Setup Prometheus metrics instrumentation
from app.core.metrics import setup_prometheus_instrumentation
prometheus_instrumentator = setup_prometheus_instrumentation(app)


# Simple middleware to limit maximum upload size (protect against huge images)
class MaxUploadSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_upload_size: int = 15 * 1024 * 1024):
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > self.max_upload_size:
                    return JSONResponse({"detail": "Request entity too large"}, status_code=413)
            except Exception:
                pass
        return await call_next(request)


# ?? Security Headers Middleware - Protects against common web vulnerabilities
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds critical security headers to all responses.
    
    Protects against:
    - Clickjacking (X-Frame-Options)
    - MIME type sniffing (X-Content-Type-Options)
    - XSS attacks (X-XSS-Protection)
    - Man-in-the-middle attacks (HSTS)
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # ? HSTS - Force HTTPS in production (max-age: 1 year, include subdomains)
        if settings.app_mode == "prod":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # ? X-Content-Type-Options - Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # ? X-Frame-Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # ? X-XSS-Protection - Enable XSS filtering in older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # ? Content-Security-Policy - Handled by GoogleOAuthCSPMiddleware
        # NOTE: CSP is applied by GoogleOAuthCSPMiddleware which handles Google OAuth 3.0
        # and differentiates between development and production environments
        
        # ? Referrer-Policy - Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # ? Permissions-Policy - Restrict browser features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
        
        return response


# CORS Configuration - STRICT in production, permissive in development
from app.core.config import settings

# Dev origins — includes both common Vite ports + 8081
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
]

if settings.app_mode == "prod":
    # Strict CORS for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-CSRF-Token",
        ],
        expose_headers=["X-Total-Count", "X-Rate-Limit-Remaining"],
        max_age=86400,
    )
else:
    # Development: explicit origins required when allow_credentials=True
    # (browsers reject allow_origins=["*"] + allow_credentials=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

# 🔐 Google OAuth CSP Middleware - MUST run before SecurityHeadersMiddleware
# This middleware applies environment-specific CSP policies optimized for Google Sign-In 3.0
# CRITICAL: Includes connect-src for CORS to Google servers + frame-src for One Tap
# IMPORTANT: Includes img-src https://*.googleusercontent.com for profile pictures
app.add_middleware(GoogleOAuthCSPMiddleware)

# 🛡️ CSRF Middleware — protects cookie-reliant endpoints (refresh, logout)
app.add_middleware(CSRFMiddleware)

# MaxUploadSize middleware added AFTER CORS (so CORS runs last)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MaxUploadSizeMiddleware)

# P3-08: GZip compression for large JSON responses (trades, rankings, lists)
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# DOC-10 §7.3 — Rate Limiting por userId / IP (100 req/min autenticado, 30 req/min anônimo)
try:
    from app.core.middleware_rate_limit import UserRateLimitMiddleware
    app.add_middleware(
        UserRateLimitMiddleware,
        jwt_secret=settings.jwt_secret_key,
        jwt_algorithm=settings.algorithm,
        redis_client=None,  # Substituído no startup após init do Redis
        user_limit=int(os.getenv("RATE_LIMIT_USER", "100")),
        ip_limit=int(os.getenv("RATE_LIMIT_IP", "30")),
        window_sec=int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60")),
    )
except Exception as _rl_exc:
    logger.warning("[WARN] UserRateLimitMiddleware não carregado: %s", _rl_exc)

# TODO: Fix error_notifier - temporarily disabled
# from app.services.error_notifier import init_notifier
# init_notifier(app)


@app.on_event("startup")
async def on_startup():
    # 🔐 Validate CREDENTIAL_ENCRYPTION_KEY — fail fast if missing or invalid
    try:
        from app.security.credential_encryption import validate_encryption_key_at_startup
        validate_encryption_key_at_startup()
    except RuntimeError as exc:
        logger.critical(str(exc))
        raise  # Abort startup; do NOT run without encryption key

    # 🔐 Validate Google OAuth configuration
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not google_client_id:
        logger.critical("=" * 80)
        logger.critical("🚨 GOOGLE OAUTH CONFIGURATION ERROR")
        logger.critical("=" * 80)
        logger.critical("ISSUE: GOOGLE_CLIENT_ID environment variable is not set")
        logger.critical("IMPACT: Google OAuth login will NOT work")
        logger.critical("ACTION: Set GOOGLE_CLIENT_ID in your .env file:")
        logger.critical("  1. Go to https://console.cloud.google.com/")
        logger.critical("  2. Create OAuth 2.0 credentials")
        logger.critical("  3. Add GOOGLE_CLIENT_ID=your_client_id to .env")
        logger.critical("=" * 80)
        logger.warning("[!] Google OAuth endpoints disabled due to missing configuration")
    else:
        logger.info(f"[OK] Google OAuth configured: {google_client_id[:20]}...")

    # [P2-12] Validate optional but important env vars — warn, never abort
    if not os.getenv("PERFECT_PAY_API_KEY"):
        logger.warning("[!] PERFECT_PAY_API_KEY not set — payment integration disabled")
    if not os.getenv("SMTP_USER") or not os.getenv("SMTP_PASS"):
        logger.warning("[!] SMTP_USER/SMTP_PASS not set — emails will only be logged (dev mode)")
    
    # [INIT] Inicializar banco SQLite local para autenticacao PRIMEIRO
    try:
        await init_local_db()
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize local SQLite database: {e}")
        raise
    
    await connect_db()  # Connect to MongoDB
    await init_db()

    # [STRATEGY_MANAGER] Recover users stuck in mid-transition states after crash
    try:
        await recover_all_users_on_startup()
    except Exception as _sm_exc:
        logger.warning(f"[WARN] StrategyManager startup recovery error (non-fatal): {_sm_exc}")

    # [ENGINE] Create trading engine indexes (idempotent — safe on every restart)
    try:
        from app.engine.migrations import create_indexes
        await create_indexes()
    except Exception as e:
        logger.warning(f"[WARN] Falha ao criar índices do engine: {e}")

    # [GAMIF] Run Gamification Database Migrations (collection + indexes)
    try:
        from app.gamification.migrations import GameificationMigrations
        await GameificationMigrations.run_all()
    except Exception as e:
        logger.error(f"[ERROR] Erro ao executar migracoes de gamificacao: {str(e)}")
        raise

    # [DOC_06] Create ranking-specific indexes (bot_trades + leaderboard_cache)
    try:
        from app.gamification.migrations import create_ranking_indexes
        await create_ranking_indexes()
    except Exception as e:
        logger.warning(f"[WARN] Falha ao criar índices de ranking: {e}")

    # [DOC_08] Create financial audit_log indexes (imutável — sem TTL)
    try:
        from app.monitoring.audit_log import create_audit_indexes
        from app.core.database import get_db as _get_db_audit
        await create_audit_indexes(_get_db_audit())
    except Exception as e:
        logger.warning(f"[WARN] Falha ao criar índices de audit_log: {e}")

    # [P2-11] Create core business collection indexes
    try:
        from app.core.db_indexes import create_core_indexes
        await create_core_indexes()
    except Exception as e:
        logger.warning(f"[WARN] Falha ao criar índices principais: {e}")

    # Admin audit trail indexes
    try:
        from app.middleware.admin_audit import create_admin_audit_indexes
        await create_admin_audit_indexes(get_db())
    except Exception as e:
        logger.warning(f"[WARN] Falha ao criar índices admin_audit_log: {e}")

    # [FASE 3] Initialize FASE 2+3 components (security, routers, database services)
    try:
        from app.initialization import init_fase_2, init_fase_3
        from app.core.database import get_db
        
        # FASE 2: Security & FastAPI integration
        init_fase_2(app, get_db())
        
        # FASE 3: Database models and services
        await init_fase_3(app, get_db())
        
        logger.info("[OK] FASE 2 and FASE 3 initialization complete")
    except Exception as e:
        logger.warning(f"[WARN] FASE 2/3 initialization error (system still operational): {str(e)}")
        # Don't raise - the rest of the system can continue without FASE 2/3
    
    # start the application scheduler (background automation)
    try:
        await core_scheduler.scheduler.start()
    except (AttributeError, Exception) as e:
        logger.warning(f"[WARN] Scheduler nao pode ser iniciado: {e}. Continuando sem scheduler...")
    
    # start the background task queue processor
    await task_queue.start_queue_processor()
    # Schedule periodic cleanup of in-memory rate limit buckets (P2-08)
    from app.core.rate_limiter import start_cleanup_scheduler
    asyncio.create_task(start_cleanup_scheduler())
    # initialize Redis connection manager for WebSocket scalability
    await redis_manager.initialize()
    # ? Start resource monitoring (CPU, Memory)
    await resource_monitor.start()

    # ⭐ DOC-01: Inicializar componentes de execução segura de ordens
    try:
        from app.trading.idempotency_store import init_idempotency_store
        from app.trading.execution_processor import init_execution_processor
        from app.trading.immutable_journal import init_immutable_journal
        from app.trading.position_manager import PositionManager
        from app.trading.reconciliation import ReconciliationJob
        from app.core.database import get_db

        _db = get_db()

        # 1. IdempotencyStore (Redis se disponível; memória como fallback)
        redis_client = getattr(redis_manager, "redis_client", None)
        idempotency_store = init_idempotency_store(redis_client)
        logger.info("[OK] IdempotencyStore inicializado (redis=%s)", redis_client is not None)

        # 2. ImmutableJournal
        journal = init_immutable_journal(_db)
        logger.info("[OK] ImmutableJournal inicializado")

        # 3. PositionManager
        position_manager = PositionManager(_db)
        app.state._position_manager = position_manager
        app.state._journal = journal
        logger.info("[OK] PositionManager inicializado")

        # 4. ExecutionProcessor (processa WS execution reports)
        init_execution_processor(
            db=_db,
            position_manager=position_manager,
            journal=journal,
        )
        logger.info("[OK] ExecutionProcessor inicializado")

        # 5. ReconciliationJob (a cada 90s sincroniza banco <-> KuCoin)
        recon_job = ReconciliationJob(
            kucoin_client=None,  # injetado per-user no método run()
            db=_db,
            journal=journal,
            interval_s=90.0,
        )
        await recon_job.start()
        app.state.reconciliation_job = recon_job
        logger.info("[OK] ReconciliationJob iniciada (intervalo=90s)")

    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar componentes DOC-01: %s", exc)
        # Não aborta o startup — sistema continua sem esses componentes

    # ── DOC-02: Take Profit / Stop Loss ──────────────────────────────────────
    try:
        from app.trading.tpsl.repository import TpSlRepository
        from app.trading.tpsl.spot_manager import init_spot_tpsl_manager
        from app.trading.tpsl.orphan_guardian import init_orphan_guardian

        _db2 = get_db()
        redis_cl = getattr(redis_manager, "redis_client", None)

        tpsl_repo = TpSlRepository(_db2)
        await tpsl_repo.ensure_indexes()
        logger.info("[OK] TpSlRepository indexes garantidos")

        # PositionManager reutilizado do bloco DOC-01 (bound via closure)
        _pm = getattr(app.state, "_position_manager", None)
        _journal = getattr(app.state, "_journal", None)

        spot_tpsl_manager = init_spot_tpsl_manager(
            kucoin_client=None,          # injetado per-user
            tpsl_repo=tpsl_repo,
            redis_client=redis_cl,
            position_manager=_pm,
            journal=_journal,
        )
        app.state.spot_tpsl_manager = spot_tpsl_manager
        logger.info("[OK] SpotTpSlManager inicializado")

        orphan_guardian = init_orphan_guardian(
            tpsl_repo=tpsl_repo,
            position_manager=_pm,
            kucoin_client=None,
            interval_s=300.0,
        )
        await orphan_guardian.start()
        app.state.orphan_guardian = orphan_guardian
        logger.info("[OK] OrphanGuardian iniciado (intervalo=300s)")

    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar componentes DOC-02: %s", exc)

    # ── DOC-03: WebSocket Profissional ────────────────────────────────────
    try:
        from app.exchanges.kucoin.ws_gateway import init_ws_gateway

        kucoin_key    = os.getenv("KUCOIN_API_KEY", "")
        kucoin_secret = os.getenv("KUCOIN_API_SECRET", "")
        kucoin_pass   = os.getenv("KUCOIN_PASSPHRASE", "")
        ws_sandbox    = os.getenv("KUCOIN_SANDBOX", "false").lower() == "true"

        redis_cl3 = getattr(redis_manager, "redis_client", None)

        ws_gateway = init_ws_gateway(
            api_key=kucoin_key or None,
            api_secret=kucoin_secret or None,
            passphrase=kucoin_pass or None,
            redis_client=redis_cl3,
            sandbox=ws_sandbox,
            subscribe_futures_orders=True,
        )
        app.state.ws_gateway = ws_gateway

        if kucoin_key:
            # Inicia com símbolos padrão; mais símbolos adicionados por bot via gateway.add_symbol()
            default_symbols = os.getenv("WS_DEFAULT_SYMBOLS", "BTC-USDT").split(",")
            default_symbols = [s.strip() for s in default_symbols if s.strip()]
            await ws_gateway.start(symbols=default_symbols)
            logger.info("[OK] WsGateway iniciado: symbols=%s", default_symbols)
        else:
            logger.info("[SKIP] WsGateway: KUCOIN_API_KEY não configurado")

    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar WsGateway (DOC-03): %s", exc)

    # ── DOC-04: Proteção contra Race Conditions ────────────────────────────
    try:
        from app.trading.distributed_lock import init_distributed_lock
        from app.trading.balance_reservation import init_balance_reservation
        from app.trading.order_queue import init_order_queue
        from app.trading.order_manager import get_order_manager as _get_om

        _redis_cl4 = getattr(redis_manager, "redis_client", None)

        # Nível 2+3: locks distribuídos e reserva de saldo
        dist_lock    = init_distributed_lock(_redis_cl4)
        balance_rsrv = init_balance_reservation(_redis_cl4)

        app.state.distributed_lock    = dist_lock
        app.state.balance_reservation = balance_rsrv

        # Injeta nas dependências do OrderManager (se já inicializado)
        try:
            _om = _get_om()
            _om._dist_lock          = dist_lock
            _om._balance_reservation = balance_rsrv
            logger.info("[OK] DOC-04 locks injetados no OrderManager existente")
        except RuntimeError:
            logger.info("[SKIP] DOC-04: OrderManager ainda não inicializado — "
                        "locks serão injetados quando ele for criado")

        # Nível 4: Redis Stream Queue (só inicia se Redis disponível)
        if _redis_cl4 is not None:
            try:
                _om_for_queue = _get_om()
                _producer, _queue_consumer = init_order_queue(
                    _redis_cl4, _om_for_queue
                )
                await _queue_consumer.start()
                app.state.order_queue_consumer = _queue_consumer
                app.state.order_queue_producer = _producer
                logger.info("[OK] OrderQueueConsumer (DOC-04 Nível 4) iniciado")
            except RuntimeError:
                logger.warning("[SKIP] DOC-04 Queue: OrderManager indisponível — "
                               "stream consumer não iniciado")
        else:
            logger.info("[SKIP] DOC-04 Queue: Redis indisponível — "
                        "OrderQueueConsumer não iniciado")

    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar componentes DOC-04: %s", exc)

    # ── DOC-05: Risk Manager Institucional ────────────────────────────────
    try:
        from app.core.database import get_db
        from app.risk.repository import RiskRepository
        from app.risk.audit_log import RiskAuditLog
        from app.risk.volatility_indexer import MarketVolatilityIndexer
        from app.risk.risk_manager import init_risk_manager
        from app.risk.daily_reset_job import DailyResetJob
        import os as _os

        _db5   = get_db()
        _redis5 = getattr(redis_manager, "redis_client", None)

        # Repositório e audit log
        _risk_repo  = RiskRepository(_db5)
        _risk_audit = RiskAuditLog(_db5)
        await _risk_repo.ensure_indexes()
        await _risk_audit.ensure_indexes()

        # Volatility indexer: tenta construir KuCoin client para dados de mercado
        _vol_kucoin = None
        try:
            from app.exchanges.kucoin.client import KuCoinClient
            _kc_key    = _os.getenv("KUCOIN_API_KEY", "")
            _kc_secret = _os.getenv("KUCOIN_API_SECRET", "")
            _kc_pass   = _os.getenv("KUCOIN_PASSPHRASE", "")
            _kc_sbox   = _os.getenv("KUCOIN_SANDBOX", "false").lower() == "true"
            if _kc_key:
                _vol_kucoin = KuCoinClient(
                    api_key=_kc_key, api_secret=_kc_secret,
                    passphrase=_kc_pass, sandbox=_kc_sbox,
                )
        except Exception as _exc_kc:
            logger.debug("DOC-05: KuCoin client para volatilidade indisponível: %s", _exc_kc)

        _vol_indexer = MarketVolatilityIndexer(_vol_kucoin, _redis5)

        # Inicializa Risk Manager global
        _risk_mgr = init_risk_manager(_redis5, _risk_repo, _risk_audit, _vol_indexer)
        app.state.risk_manager = _risk_mgr

        # Job de reset diário (00:00 UTC)
        _daily_reset = DailyResetJob(_risk_repo, kucoin_client=_vol_kucoin)
        await _daily_reset.start()
        app.state.daily_reset_job = _daily_reset

        logger.info("[OK] RiskManager (DOC-05) inicializado")

    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar RiskManager (DOC-05): %s", exc)
    # from app.services.api_monitor import init_api_monitor
    # import asyncio
    # from app.core.database import db
    # db_instance = db["trading_db"] if isinstance(db, dict) else db
    # monitor = await init_api_monitor(app, db_instance, redis_manager.redis)
    # asyncio.create_task(monitor.start_monitoring())

    # ── DOC-06: Observabilidade — HealthCheckService singleton ────────────
    try:
        from app.observability.health_check import HealthCheckService
        from app.core.database import get_database as _get_database_hc
        _hc_db = None
        try:
            _hc_db = _get_database_hc()
        except Exception:
            pass
        _health_svc = HealthCheckService(
            redis_client=redis_manager.redis_client,
            db=_hc_db,
        )
        app.state.health_service = _health_svc
        logger.info("[OK] HealthCheckService (DOC-06) inicializado")
    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar HealthCheckService (DOC-06): %s", exc)

    # ── DOC-07: LicensingService (MongoDB + Redis, sem dev bypass) ────────
    try:
        from app.licensing.service import init_licensing_service as _init_lic
        from app.core.database import get_db as _get_db_lic
        _lic_db = None
        try:
            _lic_db = _get_db_lic()
        except Exception:
            pass
        _lic_svc = _init_lic(db=_lic_db, redis=redis_manager.redis_client)
        app.state.licensing_service = _lic_svc
        # Cria índices na coleção licenses e webhook_events
        if _lic_db is not None:
            try:
                await _lic_db.licenses.create_index("user_id", unique=True)
                await _lic_db.licenses.create_index("subscription_id")
                await _lic_db.webhook_events.create_index("sale_id", unique=True)
                await _lic_db.license_audit.create_index([("user_id", 1), ("timestamp", -1)])
                logger.info("[OK] Índices licensing criados (DOC-07)")
            except Exception as _idx_exc:
                logger.debug("DOC-07: índices licensing: %s", _idx_exc)
        logger.info("[OK] LicensingService (DOC-07) inicializado")
    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar LicensingService (DOC-07): %s", exc)

    # ── DOC-08: MarketplaceService (estratégias + backtesting + revenue share) ──
    try:
        from app.strategies.marketplace import init_marketplace_service as _init_mp
        from app.core.database import get_db as _get_db_mp
        from app.core.config import settings as _cfg
        _mp_db = None
        try:
            _mp_db = _get_db_mp()
        except Exception:
            pass
        _enc_key = getattr(_cfg, "strategy_encryption_key", None)
        _take_rate = float(getattr(_cfg, "marketplace_platform_take_rate", 0.30))
        _mp_svc = _init_mp(db=_mp_db, encryption_key=_enc_key, platform_take_rate=_take_rate)
        app.state.marketplace_service = _mp_svc
        if _mp_db is not None:
            try:
                await _mp_db.strategies.create_index("strategy_id", unique=True)
                await _mp_db.strategies.create_index("creator_id")
                await _mp_db.strategies.create_index("category")
                await _mp_db.strategies.create_index([("metrics.sharpe_ratio", -1)])
                await _mp_db.strategy_subscriptions.create_index(
                    [("user_id", 1), ("strategy_id", 1)]
                )
                await _mp_db.strategy_bot_instances.create_index(
                    [("user_id", 1), ("strategy_id", 1)]
                )
                await _mp_db.strategy_trades.create_index("instance_id")
                await _mp_db.backtest_results.create_index("backtest_id", unique=True)
                await _mp_db.backtest_results.create_index("strategy_id")
                await _mp_db.revenue_events.create_index("subscription_id")
                logger.info("[OK] Índices marketplace criados (DOC-08)")
            except Exception as _idx_exc:
                logger.debug("DOC-08: índices marketplace: %s", _idx_exc)
        logger.info("[OK] MarketplaceService (DOC-08) inicializado")
    except Exception as exc:
        logger.warning("[WARN] Falha ao inicializar MarketplaceService (DOC-08): %s", exc)

    # ── Task 3.2: CircuitBreakerService (health probes + alertas) ───────────
    try:
        from app.trading.circuit_breaker_service import init_circuit_breaker_service
        cb_service = await init_circuit_breaker_service(
            exchange="kucoin",
            probe_interval_s=float(os.getenv("CB_PROBE_INTERVAL", "30")),
            failure_threshold=int(os.getenv("CB_FAILURE_THRESHOLD", "5")),
            recovery_timeout_s=float(os.getenv("CB_RECOVERY_TIMEOUT", "60")),
        )
        app.state.circuit_breaker_service = cb_service
        logger.info("[OK] CircuitBreakerService iniciado (Task 3.2)")
    except Exception as exc:
        logger.warning("[WARN] CircuitBreakerService n\u00e3o inicializado: %s", exc)

    # ── Task 3.3: AlertManager (notifica\u00e7\u00f5es de eventos cr\u00edticos) ──────────
    try:
        from app.observability.alert_manager import init_alert_manager
        from app.core.database import get_db as _get_db_alerts
        alert_mgr = init_alert_manager(
            webhook_url=os.getenv("ALERT_WEBHOOK_URL"),
            db=_get_db_alerts(),
        )
        app.state.alert_manager = alert_mgr
        # Conectar alertas ao circuit breaker
        _cb_svc = getattr(app.state, "circuit_breaker_service", None)
        if _cb_svc and alert_mgr:
            from app.observability.alert_manager import AlertSeverity
            async def _cb_alert_handler(event_type, event):
                severity = AlertSeverity.CRITICAL if "opened" in event_type else AlertSeverity.INFO
                await alert_mgr.send(
                    severity=severity,
                    title=f"Circuit Breaker: {event_type}",
                    message=str(event.get("reason", event_type)),
                    component="circuit_breaker",
                    metadata=event,
                )
            _cb_svc.on_alert(_cb_alert_handler)
        logger.info("[OK] AlertManager iniciado (Task 3.3)")
    except Exception as exc:
        logger.warning("[WARN] AlertManager n\u00e3o inicializado: %s", exc)


@app.on_event("shutdown")
async def on_shutdown():
    # ── Parar CircuitBreakerService (Task 3.2)
    try:
        from app.trading.circuit_breaker_service import shutdown_circuit_breaker_service
        await shutdown_circuit_breaker_service()
    except Exception:
        pass
    # ✅ Fechar local SQLite database
    try:
        await close_local_db()
    except Exception:
        pass
    
    # ? Stop resource monitoring and print report
    await resource_monitor.stop()
    # ? Stop API monitor
    try:
        from app.services.api_monitor import api_monitor_instance
        if api_monitor_instance:
            await api_monitor_instance.stop_monitoring()
    except Exception:
        pass
    # stop the background task queue processor
    await task_queue.stop_queue_processor()
    await core_scheduler.scheduler.shutdown()
    await disconnect_db()  # Disconnect from MongoDB
    # close Redis connection manager
    await redis_manager.close()
    # Stop any KuCoin service monitoring tasks
    try:
        await kucoin_service.stop_all()
    except Exception:
        pass
    # Parar ReconciliationJob (DOC-01)
    try:
        recon_job = getattr(app.state, "reconciliation_job", None)
        if recon_job:
            await recon_job.stop()
    except Exception:
        pass
    # Parar OrphanGuardian (DOC-02)
    try:
        guardian = getattr(app.state, "orphan_guardian", None)
        if guardian:
            await guardian.stop()
    except Exception:
        pass
    # Parar WsGateway (DOC-03)
    try:
        ws_gw = getattr(app.state, "ws_gateway", None)
        if ws_gw:
            await ws_gw.stop()
    except Exception:
        pass
    # Parar OrderQueueConsumer (DOC-04)
    try:
        oq_consumer = getattr(app.state, "order_queue_consumer", None)
        if oq_consumer:
            await oq_consumer.stop()
    except Exception:
        pass
    # Parar DailyResetJob (DOC-05)
    try:
        drj = getattr(app.state, "daily_reset_job", None)
        if drj:
            await drj.stop()
    except Exception:
        pass


@app.get(
    "/api/health",
    tags=["🩺 Health"],
    summary="Simple liveness ping",
    description="Always returns 200 with status ok if the process is alive.",
)
async def api_health():
    """Minimal liveness endpoint \u2014 always 200 while the process is running."""
    return {"status": "ok", "service": "running"}


@app.get(
    "/health",
    tags=["🩺 Health"],
    summary="Health Check Ponderado",
    description="Verificação ponderada de saúde: Redis(35) + MongoDB(30) + KuCoin(25) + WS(10).",
)
async def health(request: Request):
    """
    **Health Check Ponderado — DOC-06**

    - score >= 90 → **healthy** (HTTP 200)
    - score >= 60 → **degraded** (HTTP 200)
    - score <  60 → **unhealthy** (HTTP 503)
    """
    try:
        svc = getattr(request.app.state, "health_service", None)
        if svc is None:
            from app.observability.health_check import HealthCheckService
            svc = HealthCheckService(redis_client=redis_manager.redis_client)
        result = await svc.check()
    except Exception as exc:
        result = {"status": "unhealthy", "score": 0, "error": str(exc)}

    status_code = 503 if result.get("status") == "unhealthy" else 200
    return JSONResponse(result, status_code=status_code)


@app.get(
    "/health/ready",
    tags=["🩺 Health"],
    summary="Readiness Check (rápido)",
    description="Verifica apenas Redis e MongoDB. Retorna 503 se não pronto.",
)
async def health_ready(request: Request):
    """**Readiness — DOC-06**: apenas Redis + MongoDB, sem chamadas externas."""
    try:
        svc = getattr(request.app.state, "health_service", None)
        if svc is None:
            from app.observability.health_check import HealthCheckService
            svc = HealthCheckService(redis_client=redis_manager.redis_client)
        result = await svc.check_ready()
    except Exception as exc:
        result = {"status": "unhealthy", "score": 0, "error": str(exc)}

    status_code = 503 if result.get("status") == "unhealthy" else 200
    return JSONResponse(result, status_code=status_code)


@app.get(
    "/metrics",
    tags=["🩺 Health"],
    summary="Prometheus Metrics",
    description="Expõe todas as métricas Prometheus (core + trading_).",
    include_in_schema=False,
)
async def prometheus_metrics():
    """**Prometheus /metrics — DOC-06**: combina core/metrics.py e observability/metrics.py."""
    try:
        from app.observability.metrics import get_all_metrics
        data, content_type = await get_all_metrics()
        return Response(content=data, media_type=content_type)
    except Exception as exc:
        return Response(
            content=f"# metrics error: {exc}\n",
            media_type="text/plain",
            status_code=500,
        )


@app.get(
    "/health/dashboard",
    tags=["🩺 Health"],
    summary="Dashboard consolidado do sistema",
    description="Retorna visão unificada: health, circuit breaker, alertas, recursos.",
)
async def system_dashboard(request: Request):
    """
    **System Dashboard — Task 3.3**

    Consolida status de todos os componentes em um único endpoint:
    - Health check ponderado
    - Estado do circuit breaker
    - Alertas recentes
    - Uso de recursos (memória, CPU)
    - Métricas de execução
    """
    dashboard: dict = {"timestamp": datetime.utcnow().isoformat()}

    # 1. Health check
    try:
        svc = getattr(request.app.state, "health_service", None)
        if svc is None:
            from app.observability.health_check import HealthCheckService
            svc = HealthCheckService(redis_client=redis_manager.redis_client)
        dashboard["health"] = await svc.check()
    except Exception as exc:
        dashboard["health"] = {"status": "unknown", "error": str(exc)}

    # 2. Circuit breaker
    try:
        cb_svc = getattr(request.app.state, "circuit_breaker_service", None)
        if cb_svc:
            dashboard["circuit_breaker"] = cb_svc.status()
        else:
            dashboard["circuit_breaker"] = {"state": "not_initialized"}
    except Exception as exc:
        dashboard["circuit_breaker"] = {"error": str(exc)}

    # 3. Alertas recentes
    try:
        alert_mgr = getattr(request.app.state, "alert_manager", None)
        if alert_mgr:
            dashboard["alerts"] = {
                "recent": alert_mgr.get_recent(10),
                "stats": alert_mgr.stats(),
            }
        else:
            dashboard["alerts"] = {"status": "not_initialized"}
    except Exception as exc:
        dashboard["alerts"] = {"error": str(exc)}

    # 4. Recursos
    try:
        from app.core.monitoring import resource_monitor
        snapshots = resource_monitor.snapshots
        if snapshots:
            last = snapshots[-1]
            dashboard["resources"] = {
                "memory_rss_mb": last.memory_rss_mb,
                "memory_percent": last.memory_percent,
                "cpu_percent": last.cpu_percent,
                "num_threads": last.num_threads,
            }
        else:
            dashboard["resources"] = {"status": "no_data"}
    except Exception as exc:
        dashboard["resources"] = {"error": str(exc)}

    # 5. Reconciliation
    try:
        recon_job = getattr(request.app.state, "reconciliation_job", None)
        if recon_job:
            dashboard["reconciliation"] = {"running": True}
        else:
            dashboard["reconciliation"] = {"running": False}
    except Exception:
        dashboard["reconciliation"] = {"running": False}

    return JSONResponse(dashboard)


# ============================================
# ? Registrar Routers com Tags
# ============================================

# Auth & Users
app.include_router(auth_router.router, tags=["? Auth"])
app.include_router(two_factor_router, prefix="/api", tags=["? Auth"])
app.include_router(settings_router, tags=["? Users"])
app.include_router(license_router, tags=["?? Admin"])
app.include_router(me_router.router, tags=["? Users"])
app.include_router(forgot_password_router, tags=["🔑 Auth - Password Reset"])
app.include_router(lgpd_router, tags=["🔒 LGPD"])

# Strategy Manager (Single Active Strategy Mode)
app.include_router(strategy_manager_router, tags=["🤖 Strategy Manager"])

# Bots & Trading
app.include_router(bots_router.router, tags=["? Bots"])
app.include_router(chat_router.router, tags=["? Chat"])
app.include_router(execution_router, tags=["? Bots"])
app.include_router(trading_router.router, tags=["? Trading"])
app.include_router(audit_router, prefix="/api", tags=["? Trading"])
app.include_router(validation_router, prefix="/api", tags=["? Trading"])
app.include_router(kill_switch_router, tags=["?? Admin"])

# Engine Health (PEND-03)
try:
    from app.trading.engine_health_router import router as _engine_health_router
    app.include_router(_engine_health_router, tags=["🔧 Engine Health"])
except Exception as _eh_exc:
    logger.warning("Engine health router not loaded: %s", _eh_exc)

# Analytics & Strategies
app.include_router(analytics_router.router, tags=["? Analytics"])
app.include_router(strategies_router.router, tags=["? Strategies"])

# DOC-08: Backtesting Engine
try:
    from app.strategies.backtest_router import router as _backtest_router
    app.include_router(_backtest_router, tags=["📊 Backtest"])
except Exception as _bt_exc:
    logger.warning("Backtest router not loaded: %s", _bt_exc)

# DOC-08: Marketplace de Estratégias
try:
    from app.strategies.marketplace_router import router as _marketplace_router
    app.include_router(_marketplace_router, tags=["📈 Marketplace"])
except Exception as _mp_exc:
    logger.warning("[WARN] Marketplace router não carregado: %s", _mp_exc)

# PricePro EA (MQL5 → KuCoin microservice)
try:
    from app.strategies.pricepro_ea.router import router as _pricepro_router
    app.include_router(_pricepro_router, tags=["🤖 PricePro EA"])
except Exception as _pp_exc:
    logger.warning("[WARN] PricePro EA router não carregado: %s", _pp_exc)

# Gamification (Arena de Lucros)
app.include_router(gamification_router.router, tags=["🎮 Gamification"])

# EA Monitor — MetaTrader MT4/MT5 Integration (PEND-13)
app.include_router(ea_monitor_router, tags=["📡 EA Monitor"])
app.include_router(ea_monitor_ws_router, tags=["📡 EA Monitor WebSocket"])

# Robot Marketplace — Purchase / Performance / Review (PEND-14)
app.include_router(marketplace_robots_router, tags=["🛒 Robot Marketplace"])

# Notifications
app.include_router(notifications_router.router, tags=["? Notifications"])
app.include_router(ws_notifications_router, tags=["? Notifications"])
# Test realtime helpers (dev only)
app.include_router(test_realtime_router.router, tags=["? Test Realtime"])

# Affiliates & Education
app.include_router(affiliates_router.router, tags=["? Affiliates"])
app.include_router(education_router.router, tags=["? Education"])

# Billing (Perfect Pay postbacks)
app.include_router(billing_router, tags=["💳 Billing"])

# Billing Management (subscription lifecycle + admin revenue)
try:
    from app.billing.router import router as _billing_mgmt_router, admin_router as _billing_admin_router
    app.include_router(_billing_mgmt_router, tags=["💳 Billing Management"])
    app.include_router(_billing_admin_router, tags=["💳 Admin Billing"])
except Exception as _bm_exc:
    logger.warning("Billing management routers not loaded: %s", _bm_exc)

# Core
app.include_router(core_router.router, prefix="/api", tags=["?? Admin"])

# DOC-08: Monitoring — /health/detailed
try:
    from app.monitoring.health import health_router as _health_router
    app.include_router(_health_router, tags=["❤️ Health"])
except Exception as _e:
    logger.warning(f"health_router não registrado: {_e}")

try:
    from app.trading.bots_history_router import router as _bots_history_router
    app.include_router(_bots_history_router, tags=["📊 Bot History"])
except Exception as _hm_exc:
    logger.warning("[WARN] monitoring/health router nao carregado: %s", _hm_exc)


@app.get(
    "/me",
    tags=["? Users"],
    summary="Dados do Usu?rio Atual",
    description="Retorna informa??es do usu?rio autenticado.",
    responses={
        200: {
            "description": "Dados do usu?rio",
            "content": {
                "application/json": {
                    "example": {
                        "id": "user_123",
                        "email": "usuario@exemplo.com",
                        "is_active": True,
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        401: {"description": "N?o autenticado"}
    }
)
async def me(current_user=Depends(get_current_user)):
    """
    **Obter Dados do Usu?rio Atual**
    
    Retorna as informa??es b?sicas do usu?rio autenticado.
    
    Requer token JWT v?lido no header Authorization.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
    }
