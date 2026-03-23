"""
Error Notifier Service
Sends alerts to Discord/Slack webhooks on critical errors and events
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

import aiohttp
from fastapi import FastAPI
from pydantic import BaseModel

# ============================================================================
# Models
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorAlert(BaseModel):
    """Error alert data"""
    severity: AlertSeverity
    title: str
    message: str
    error_code: Optional[int] = None
    endpoint: Optional[str] = None
    user_id: Optional[str] = None
    stacktrace: Optional[str] = None
    timestamp: Optional[str] = None
    tags: Optional[Dict[str, str]] = None


class EventAlert(BaseModel):
    """General event alert"""
    severity: AlertSeverity
    title: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


# ============================================================================
# Error Notifier Class
# ============================================================================

class ErrorNotifier:
    """
    Sends notifications to Discord and/or Slack webhooks
    Supports both async and sync operations
    """

    def __init__(
        self,
        discord_webhook_url: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        project_name: str = "Crypto Trade Hub",
        environment: str = "production",
    ):
        """
        Initialize error notifier

        Args:
            discord_webhook_url: Discord webhook URL
            slack_webhook_url: Slack webhook URL
            project_name: Project name for alerts
            environment: Environment name (dev/staging/production)
        """
        self.discord_webhook_url = discord_webhook_url or os.getenv(
            "DISCORD_WEBHOOK_URL"
        )
        self.slack_webhook_url = slack_webhook_url or os.getenv(
            "SLACK_WEBHOOK_URL"
        )
        self.project_name = project_name
        self.environment = environment

        if not self.discord_webhook_url and not self.slack_webhook_url:
            print(
                "[WARNING] No webhook URLs configured. Errors won't be notified."
            )

    # ========================================================================
    # Discord Methods
    # ========================================================================

    def _build_discord_embed(
        self, alert: ErrorAlert | EventAlert
    ) -> Dict[str, Any]:
        """Build Discord embed from alert"""

        # Color based on severity
        colors = {
            AlertSeverity.INFO: 3447003,  # Blue
            AlertSeverity.WARNING: 15105570,  # Yellow
            AlertSeverity.ERROR: 15158332,  # Orange
            AlertSeverity.CRITICAL: 16711680,  # Red
        }

        timestamp = alert.timestamp or datetime.utcnow().isoformat()

        embed = {
            "title": f"{alert.title}",
            "description": alert.message,
            "color": colors.get(alert.severity, 3447003),
            "timestamp": timestamp,
            "footer": {
                "text": f"{self.project_name} ? {self.environment.upper()}"
            },
            "fields": [],
        }

        # Add severity badge
        embed["fields"].append(
            {
                "name": "Severity",
                "value": alert.severity.upper(),
                "inline": True,
            }
        )

        # Add error-specific fields
        if isinstance(alert, ErrorAlert):
            if alert.error_code:
                embed["fields"].append(
                    {
                        "name": "Error Code",
                        "value": str(alert.error_code),
                        "inline": True,
                    }
                )

            if alert.endpoint:
                embed["fields"].append(
                    {
                        "name": "Endpoint",
                        "value": f"`{alert.endpoint}`",
                        "inline": True,
                    }
                )

            if alert.user_id:
                embed["fields"].append(
                    {
                        "name": "User ID",
                        "value": alert.user_id,
                        "inline": True,
                    }
                )

            if alert.tags:
                for key, value in alert.tags.items():
                    embed["fields"].append(
                        {
                            "name": key.title(),
                            "value": str(value),
                            "inline": True,
                        }
                    )

            # Add stacktrace as code block (max 1000 chars)
            if alert.stacktrace:
                stacktrace_block = alert.stacktrace[-1000:]
                embed["fields"].append(
                    {
                        "name": "Stacktrace",
                        "value": f"```\n{stacktrace_block}\n```",
                        "inline": False,
                    }
                )

        # Add event-specific fields
        elif isinstance(alert, EventAlert):
            if alert.details:
                for key, value in alert.details.items():
                    embed["fields"].append(
                        {
                            "name": key.title(),
                            "value": str(value)[:256],
                            "inline": True,
                        }
                    )

        return embed

    async def send_to_discord(self, alert: ErrorAlert | EventAlert) -> bool:
        """Send alert to Discord (async)"""

        if not self.discord_webhook_url:
            return False

        try:
            embed = self._build_discord_embed(alert)
            payload = {"embeds": [embed]}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.discord_webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in (200, 204):
                        return True
                    else:
                        print(
                            f"Discord notification failed: {response.status}"
                        )
                        return False

        except asyncio.TimeoutError:
            print("Discord notification timeout")
            return False
        except Exception as e:
            print(f"Discord notification error: {e}")
            return False

    # ========================================================================
    # Slack Methods
    # ========================================================================

    def _build_slack_message(self, alert: ErrorAlert | EventAlert) -> Dict[str, Any]:
        """Build Slack message from alert"""

        # Color based on severity
        colors = {
            AlertSeverity.INFO: "#36a64f",  # Green
            AlertSeverity.WARNING: "#ff9900",  # Orange
            AlertSeverity.ERROR: "#ff6600",  # Red-orange
            AlertSeverity.CRITICAL: "#cc0000",  # Red
        }

        timestamp = alert.timestamp or datetime.utcnow().isoformat()

        message = {
            "attachments": [
                {
                    "color": colors.get(alert.severity, "#36a64f"),
                    "title": alert.title,
                    "text": alert.message,
                    "mrkdwn_in": ["text", "fields"],
                    "fields": [],
                    "footer": f"{self.project_name} ? {self.environment.upper()}",
                    "ts": int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()),
                }
            ]
        }

        attachment = message["attachments"][0]

        # Add severity
        attachment["fields"].append(
            {
                "title": "Severity",
                "value": alert.severity.upper(),
                "short": True,
            }
        )

        # Error-specific fields
        if isinstance(alert, ErrorAlert):
            if alert.error_code:
                attachment["fields"].append(
                    {
                        "title": "Error Code",
                        "value": str(alert.error_code),
                        "short": True,
                    }
                )

            if alert.endpoint:
                attachment["fields"].append(
                    {
                        "title": "Endpoint",
                        "value": f"`{alert.endpoint}`",
                        "short": True,
                    }
                )

            if alert.user_id:
                attachment["fields"].append(
                    {
                        "title": "User ID",
                        "value": alert.user_id,
                        "short": True,
                    }
                )

            if alert.tags:
                for key, value in alert.tags.items():
                    attachment["fields"].append(
                        {
                            "title": key.title(),
                            "value": str(value),
                            "short": True,
                        }
                    )

            if alert.stacktrace:
                stacktrace_block = alert.stacktrace[-800:]
                attachment["fields"].append(
                    {
                        "title": "Stacktrace",
                        "value": f"```\n{stacktrace_block}\n```",
                        "short": False,
                    }
                )

        # Event-specific fields
        elif isinstance(alert, EventAlert):
            if alert.details:
                for key, value in alert.details.items():
                    attachment["fields"].append(
                        {
                            "title": key.title(),
                            "value": str(value)[:256],
                            "short": True,
                        }
                    )

        return message

    async def send_to_slack(self, alert: ErrorAlert | EventAlert) -> bool:
        """Send alert to Slack (async)"""

        if not self.slack_webhook_url:
            return False

        try:
            message = self._build_slack_message(alert)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook_url, json=message, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        return True
                    else:
                        print(f"Slack notification failed: {response.status}")
                        return False

        except asyncio.TimeoutError:
            print("Slack notification timeout")
            return False
        except Exception as e:
            print(f"Slack notification error: {e}")
            return False

    # ========================================================================
    # Public Methods
    # ========================================================================

    async def notify_error(
        self,
        title: str,
        message: str,
        error_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        stacktrace: Optional[str] = None,
        severity: AlertSeverity = AlertSeverity.ERROR,
        tags: Optional[Dict[str, str]] = None,
    ) -> tuple[bool, bool]:
        """
        Send error notification to Discord and Slack

        Returns:
            Tuple[discord_sent, slack_sent]
        """

        alert = ErrorAlert(
            severity=severity,
            title=title,
            message=message,
            error_code=error_code,
            endpoint=endpoint,
            user_id=user_id,
            stacktrace=stacktrace,
            tags=tags,
        )

        # Send to both platforms concurrently
        discord_result, slack_result = await asyncio.gather(
            self.send_to_discord(alert),
            self.send_to_slack(alert),
            return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(discord_result, Exception):
            print(f"Discord error: {discord_result}")
            discord_result = False

        if isinstance(slack_result, Exception):
            print(f"Slack error: {slack_result}")
            slack_result = False

        return bool(discord_result), bool(slack_result)

    async def notify_event(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.INFO,
        details: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, bool]:
        """
        Send event notification to Discord and Slack

        Returns:
            Tuple[discord_sent, slack_sent]
        """

        alert = EventAlert(
            severity=severity,
            title=title,
            message=message,
            details=details,
        )

        # Send to both platforms concurrently
        discord_result, slack_result = await asyncio.gather(
            self.send_to_discord(alert),
            self.send_to_slack(alert),
            return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(discord_result, Exception):
            print(f"Discord error: {discord_result}")
            discord_result = False

        if isinstance(slack_result, Exception):
            print(f"Slack error: {slack_result}")
            slack_result = False

        return bool(discord_result), bool(slack_result)

    async def notify_kill_switch_activated(
        self,
        user_id: str,
        reason: str,
        triggered_by: Optional[str] = None,
    ) -> tuple[bool, bool]:
        """Send Kill Switch activation alert (always CRITICAL)"""

        details = {
            "user_id": user_id,
            "reason": reason,
        }

        if triggered_by:
            details["triggered_by"] = triggered_by

        return await self.notify_event(
            title="? Kill Switch Activated",
            message=f"Emergency stop triggered for user {user_id}",
            severity=AlertSeverity.CRITICAL,
            details=details,
        )

    async def notify_api_balance_low(
        self,
        user_id: str,
        exchange: str,
        balance: float,
        minimum_required: float,
    ) -> tuple[bool, bool]:
        """Send low API balance alert"""

        return await self.notify_event(
            title="?? Low API Balance",
            message=f"API balance for {exchange} is below minimum threshold",
            severity=AlertSeverity.WARNING,
            details={
                "user_id": user_id,
                "exchange": exchange,
                "current_balance": f"${balance:.2f}",
                "minimum_required": f"${minimum_required:.2f}",
            },
        )

    async def notify_api_key_invalid(
        self,
        user_id: str,
        exchange: str,
        bot_id: Optional[str] = None,
    ) -> tuple[bool, bool]:
        """Send invalid API key alert"""

        details = {
            "user_id": user_id,
            "exchange": exchange,
        }

        if bot_id:
            details["bot_id"] = bot_id

        return await self.notify_event(
            title="? Invalid API Key",
            message=f"API key validation failed for {exchange}",
            severity=AlertSeverity.ERROR,
            details=details,
        )


# ============================================================================
# Singleton Instance
# ============================================================================

_notifier_instance: Optional[ErrorNotifier] = None


def get_notifier() -> ErrorNotifier:
    """Get or create error notifier singleton"""
    global _notifier_instance

    if _notifier_instance is None:
        _notifier_instance = ErrorNotifier(
            environment=os.getenv("ENVIRONMENT", "production")
        )

    return _notifier_instance


def init_notifier(app: FastAPI) -> None:
    """Initialize error notifier with FastAPI app"""

    notifier = get_notifier()
    
    # Import here to avoid circular imports
    from starlette.middleware.base import BaseHTTPMiddleware

    class ErrorHandlingMiddleware(BaseHTTPMiddleware):
        """Middleware to catch and notify errors"""
        
        async def dispatch(self, request, call_next):
            try:
                response = await call_next(request)

                # Notify on 500+ errors
                if response.status_code >= 500:
                    try:
                        body = b""
                        async for chunk in response.body_iterator:
                            body += chunk

                        await notifier.notify_error(
                            title=f"HTTP {response.status_code}",
                            message=f"Error on {request.method} {request.url.path}",
                            error_code=response.status_code,
                            endpoint=str(request.url.path),
                            user_id=request.headers.get("X-User-ID"),
                            severity=AlertSeverity.ERROR,
                            tags={
                                "method": request.method,
                                "path": request.url.path,
                                "status": str(response.status_code),
                            },
                        )

                        # Return modified response
                        from starlette.responses import Response

                        return Response(
                            content=body,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            media_type=response.media_type,
                        )
                    except Exception as e:
                        print(f"Error in middleware: {e}")
                        return response

                return response

            except Exception as e:
                import traceback

                await notifier.notify_error(
                    title="Unhandled Exception",
                    message=str(e),
                    endpoint=str(request.url.path),
                    user_id=request.headers.get("X-User-ID"),
                    stacktrace=traceback.format_exc(),
                    severity=AlertSeverity.CRITICAL,
                    tags={
                        "method": request.method,
                        "path": request.url.path,
                        "error_type": type(e).__name__,
                    },
                )

                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error"},
                )

    # Add middleware BEFORE app startup
    app.add_middleware(ErrorHandlingMiddleware)
    print("[OK] Error notifier initialized")
