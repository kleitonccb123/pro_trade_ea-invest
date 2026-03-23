"""
Sistema de Alertas — DOC-08 §5

Envia notificações via Telegram quando eventos críticos ocorrem.

Configuração (variáveis de ambiente):
  TELEGRAM_BOT_TOKEN — token do bot Telegram
  TELEGRAM_CHAT_ID   — chat ID de destino (grupo ou canal)

Uso::

    from app.monitoring.alerting import TelegramAlerter, AlertLevel
    from app.monitoring.alerting import alert_bot_stopped_by_risk

    alerter = TelegramAlerter(bot_token="...", chat_id="...")

    # Alerta genérico
    await alerter.send("Sistema operacional.", AlertLevel.INFO)

    # Alertas semânticos
    await alert_bot_stopped_by_risk(alerter, "u1", "BotRSI", "daily_drawdown", -5.23)
    await alert_kucoin_connectivity_lost(alerter, minutes_offline=15)
    await alert_high_error_rate(alerter, errors_per_min=30)

    # Singleton via env vars
    alerter = TelegramAlerter.from_env()
    if alerter:
        await alerter.send("Pronto.", AlertLevel.INFO)
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger("alerting")


class AlertLevel(str, Enum):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"


_LEVEL_EMOJI = {
    AlertLevel.INFO:     "ℹ️",
    AlertLevel.WARNING:  "⚠️",
    AlertLevel.CRITICAL: "🚨",
}


class TelegramAlerter:
    """
    Envia mensagens para um chat/grupo/canal Telegram.

    Suporta formatação Markdown e retry simples (1 tentativa).
    Silencia erros de rede — alertas não devem crashar o sistema.
    """

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id   = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    @classmethod
    def from_env(cls) -> Optional["TelegramAlerter"]:
        """
        Cria instância a partir das variáveis de ambiente.
        Retorna None se as variáveis não estiverem configuradas.
        """
        token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            return None
        return cls(bot_token=token, chat_id=chat_id)

    async def send(
        self,
        message: str,
        level: AlertLevel = AlertLevel.INFO,
    ) -> bool:
        """
        Envia mensagem Telegram.

        Retorna True se enviado com sucesso, False em caso de erro.
        Nunca propaga exceções — falha silenciosa para não interromper o fluxo.
        """
        emoji = _LEVEL_EMOJI.get(level, "ℹ️")
        text  = f"{emoji} *CryptoTradeHub Alert*\n\n{message}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    self._base_url,
                    json={
                        "chat_id":    self.chat_id,
                        "text":       text,
                        "parse_mode": "Markdown",
                    },
                )
                if resp.status_code == 200:
                    return True
                logger.warning("TelegramAlerter: status=%d body=%s", resp.status_code, resp.text[:200])
                return False

        except Exception as exc:
            logger.error("TelegramAlerter: falha ao enviar alerta: %s", exc)
            return False

    async def send_plain(self, message: str) -> bool:
        """Envia texto simples sem formatação Markdown (fallback seguro)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    self._base_url,
                    json={
                        "chat_id": self.chat_id,
                        "text":    message,
                    },
                )
                return resp.status_code == 200
        except Exception as exc:
            logger.error("TelegramAlerter.send_plain: %s", exc)
            return False


# ─── Alertas padronizados ─────────────────────────────────────────────────────


async def alert_bot_stopped_by_risk(
    alerter: TelegramAlerter,
    user_id: str,
    bot_name: str,
    reason: str,
    pnl: float,
) -> None:
    """Alerta quando um bot é parado automaticamente pelo Risk Manager."""
    await alerter.send(
        f"Bot *{bot_name}* do usuário `{user_id}` foi parado por risco.\n"
        f"Motivo: `{reason}`\n"
        f"PnL da sessão: `{pnl:+.4f} USDT`",
        AlertLevel.CRITICAL,
    )


async def alert_kucoin_connectivity_lost(
    alerter: TelegramAlerter,
    minutes_offline: int,
) -> None:
    """Alerta quando a KuCoin API fica inacessível por um período."""
    await alerter.send(
        f"KuCoin API inacessível há *{minutes_offline} minutos*.\n"
        f"Todos os bots foram pausados.",
        AlertLevel.CRITICAL,
    )


async def alert_high_error_rate(
    alerter: TelegramAlerter,
    errors_per_min: int,
) -> None:
    """Alerta quando a taxa de erros excede um limiar."""
    await alerter.send(
        f"Taxa de erros elevada: *{errors_per_min} erros/min*.\n"
        f"Investigar imediatamente.",
        AlertLevel.WARNING,
    )


async def alert_error_burst_detected(
    alerter: TelegramAlerter,
    bot_id: str,
    user_id: str,
    error_count: int,
    window_seconds: int,
) -> None:
    """Alerta quando um bot aciona o circuit-breaker de error burst."""
    await alerter.send(
        f"Bot `{bot_id[:12]}` (user `{user_id}`) parado por error burst.\n"
        f"*{error_count} erros* em {window_seconds}s.",
        AlertLevel.CRITICAL,
    )


async def alert_global_kill_switch_activated(
    alerter: TelegramAlerter,
    activated_by: str,
) -> None:
    """Alerta quando o kill switch global é acionado por um admin."""
    await alerter.send(
        f"🔴 *KILL SWITCH GLOBAL ATIVADO* por `{activated_by}`.\n"
        f"Todos os bots da plataforma serão parados.",
        AlertLevel.CRITICAL,
    )
