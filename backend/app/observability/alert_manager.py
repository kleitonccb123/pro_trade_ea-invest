"""
AlertManager — Task 3.3

Sistema de alertas para eventos críticos do sistema de trading.

Canais suportados:
  1. Logging estruturado (sempre ativo)
  2. Webhook (POST para URL configurável)
  3. MongoDB (persistência para auditoria)
  4. In-memory (para dashboard em tempo real)

Quando alerta:
  - Circuit breaker abriu (exchange offline)
  - Circuit breaker fechou (recovery)
  - Kill-switch ativado
  - Ordem falhou N vezes consecutivas
  - Daily loss limit atingido
  - Reconciliação encontrou divergência
  - Health score caiu abaixo de threshold

Integração:
    from app.observability.alert_manager import (
        init_alert_manager, get_alert_manager, AlertSeverity
    )

    alert_mgr = get_alert_manager()
    await alert_mgr.send(
        severity=AlertSeverity.CRITICAL,
        title="Circuit Breaker Aberto",
        message="KuCoin não responde após 5 falhas consecutivas",
        component="circuit_breaker",
        metadata={"exchange": "kucoin", "consecutive_fails": 5}
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Níveis de severidade de alerta."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertChannel(str, Enum):
    """Canais de entrega de alertas."""
    LOG = "log"
    WEBHOOK = "webhook"
    DATABASE = "database"


class Alert:
    """Representa um alerta individual."""

    __slots__ = (
        "id", "severity", "title", "message", "component",
        "metadata", "timestamp", "acknowledged", "channels_sent",
    )

    _counter = 0

    def __init__(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        component: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        Alert._counter += 1
        self.id = f"alert_{Alert._counter}_{int(datetime.utcnow().timestamp())}"
        self.severity = severity
        self.title = title
        self.message = message
        self.component = component
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
        self.acknowledged = False
        self.channels_sent: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "component": self.component,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "channels_sent": self.channels_sent,
        }


class AlertManager:
    """
    Gerenciador central de alertas do sistema.

    Despacha alertas para múltiplos canais e mantém histórico em memória
    para consulta via dashboard.
    """

    def __init__(
        self,
        *,
        webhook_url: Optional[str] = None,
        db: Optional[Any] = None,
        max_history: int = 500,
        cooldown_s: float = 300.0,
    ) -> None:
        """
        Args:
            webhook_url: URL para POST de alertas (None = desabilitado)
            db: Database Motor para persistência (None = desabilitado)
            max_history: Máximo de alertas em memória
            cooldown_s: Cooldown entre alertas iguais (evita spam)
        """
        self._webhook_url = webhook_url
        self._db = db
        self._max_history = max_history
        self._cooldown_s = cooldown_s

        # Histórico em memória
        self._alerts: List[Alert] = []

        # Cooldown: key=(severity, title, component) → last_sent
        self._cooldowns: Dict[str, datetime] = {}

        # Contadores
        self._total_sent = 0
        self._total_suppressed = 0

        logger.info(
            f"AlertManager inicializado "
            f"(webhook={'ON' if webhook_url else 'OFF'}, "
            f"db={'ON' if db else 'OFF'}, "
            f"cooldown={cooldown_s}s)"
        )

    # ─────────────────── API Principal ───────────────────

    async def send(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        component: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """
        Envia um alerta para todos os canais configurados.

        Returns:
            Alert se enviado, None se suprimido por cooldown
        """
        # Verificar cooldown
        cooldown_key = f"{severity.value}:{title}:{component}"
        if self._is_in_cooldown(cooldown_key):
            self._total_suppressed += 1
            logger.debug(f"Alerta suprimido (cooldown): {title}")
            return None

        # Criar alerta
        alert = Alert(
            severity=severity,
            title=title,
            message=message,
            component=component,
            metadata=metadata,
        )

        # Registrar cooldown
        self._cooldowns[cooldown_key] = datetime.utcnow()

        # Despachar para canais
        await self._dispatch_log(alert)
        await self._dispatch_webhook(alert)
        await self._dispatch_database(alert)

        # Armazenar em memória
        self._alerts.append(alert)
        if len(self._alerts) > self._max_history:
            self._alerts = self._alerts[-self._max_history:]

        self._total_sent += 1
        return alert

    # ─────────────────── Convenience Methods ───────────────────

    async def info(self, title: str, message: str, **kwargs) -> Optional[Alert]:
        return await self.send(AlertSeverity.INFO, title, message, **kwargs)

    async def warning(self, title: str, message: str, **kwargs) -> Optional[Alert]:
        return await self.send(AlertSeverity.WARNING, title, message, **kwargs)

    async def critical(self, title: str, message: str, **kwargs) -> Optional[Alert]:
        return await self.send(AlertSeverity.CRITICAL, title, message, **kwargs)

    async def emergency(self, title: str, message: str, **kwargs) -> Optional[Alert]:
        return await self.send(AlertSeverity.EMERGENCY, title, message, **kwargs)

    # ─────────────────── Dispatch Channels ───────────────────

    async def _dispatch_log(self, alert: Alert) -> None:
        """Canal 1: Logging estruturado."""
        log_map = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.CRITICAL: logger.critical,
            AlertSeverity.EMERGENCY: logger.critical,
        }
        log_fn = log_map.get(alert.severity, logger.info)
        log_fn(
            f"[ALERTA {alert.severity.value.upper()}] "
            f"{alert.title} — {alert.message} "
            f"(component={alert.component})"
        )
        alert.channels_sent.append(AlertChannel.LOG.value)

    async def _dispatch_webhook(self, alert: Alert) -> None:
        """Canal 2: Webhook POST."""
        if not self._webhook_url:
            return

        try:
            import aiohttp
            payload = {
                "text": f"[{alert.severity.value.upper()}] {alert.title}\n{alert.message}",
                "severity": alert.severity.value,
                "component": alert.component,
                "timestamp": alert.timestamp.isoformat(),
                "metadata": alert.metadata,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status < 300:
                        alert.channels_sent.append(AlertChannel.WEBHOOK.value)
                    else:
                        logger.warning(
                            f"Webhook retornou {resp.status} para alerta {alert.id}"
                        )
        except ImportError:
            logger.debug("aiohttp não disponível para webhook")
        except Exception as exc:
            logger.error(f"Erro ao enviar webhook: {exc}")

    async def _dispatch_database(self, alert: Alert) -> None:
        """Canal 3: Persistência em MongoDB."""
        if not self._db:
            return

        try:
            await self._db.system_alerts.insert_one(alert.to_dict())
            alert.channels_sent.append(AlertChannel.DATABASE.value)
        except Exception as exc:
            logger.error(f"Erro ao persistir alerta no DB: {exc}")

    # ─────────────────── Cooldown ───────────────────

    def _is_in_cooldown(self, key: str) -> bool:
        """Verifica se alerta ainda está em cooldown."""
        last_sent = self._cooldowns.get(key)
        if not last_sent:
            return False
        elapsed = (datetime.utcnow() - last_sent).total_seconds()
        return elapsed < self._cooldown_s

    def _cleanup_cooldowns(self) -> None:
        """Remove cooldowns expirados."""
        now = datetime.utcnow()
        cutoff = timedelta(seconds=self._cooldown_s * 2)
        self._cooldowns = {
            k: v for k, v in self._cooldowns.items()
            if (now - v) < cutoff
        }

    # ─────────────────── Query / Dashboard ───────────────────

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna alertas recentes para dashboard."""
        return [a.to_dict() for a in self._alerts[-limit:]]

    def get_by_severity(self, severity: AlertSeverity) -> List[Dict[str, Any]]:
        """Filtra alertas por severidade."""
        return [
            a.to_dict() for a in self._alerts
            if a.severity == severity
        ]

    def get_unacknowledged(self) -> List[Dict[str, Any]]:
        """Retorna alertas não reconhecidos."""
        return [a.to_dict() for a in self._alerts if not a.acknowledged]

    def acknowledge(self, alert_id: str) -> bool:
        """Marca alerta como reconhecido."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def stats(self) -> Dict[str, Any]:
        """Estatísticas do alert manager."""
        severity_counts = {}
        for alert in self._alerts:
            key = alert.severity.value
            severity_counts[key] = severity_counts.get(key, 0) + 1

        return {
            "total_sent": self._total_sent,
            "total_suppressed": self._total_suppressed,
            "in_memory": len(self._alerts),
            "unacknowledged": sum(1 for a in self._alerts if not a.acknowledged),
            "by_severity": severity_counts,
            "webhook_enabled": bool(self._webhook_url),
            "db_enabled": bool(self._db),
            "cooldown_s": self._cooldown_s,
        }


# ═══════════════════════════════════════════════════════════════════════
# Singleton global
# ═══════════════════════════════════════════════════════════════════════

_alert_manager: Optional[AlertManager] = None


def init_alert_manager(
    *,
    webhook_url: Optional[str] = None,
    db: Optional[Any] = None,
    cooldown_s: float = 300.0,
) -> AlertManager:
    """Inicializa o AlertManager global."""
    global _alert_manager
    _alert_manager = AlertManager(
        webhook_url=webhook_url or os.getenv("ALERT_WEBHOOK_URL"),
        db=db,
        cooldown_s=cooldown_s,
    )
    return _alert_manager


def get_alert_manager() -> Optional[AlertManager]:
    """Retorna o AlertManager global, ou None."""
    return _alert_manager
