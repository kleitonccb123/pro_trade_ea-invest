"""
Critical Log Handler with Error Notification

Integrates Python logging system with ErrorNotifier to send immediate
Discord/Slack alerts when CRITICAL logs are encountered.

This ensures operators are notified of serious issues in production
(e.g., database fallback to SQLite, missing credentials, etc.)
"""

import logging
import os
import asyncio
from typing import Optional

from app.services.error_notifier import ErrorNotifier, AlertSeverity, ErrorAlert


class ErrorNotifierHandler(logging.Handler):
    """
    Custom logging handler that sends CRITICAL and ERROR logs to Discord/Slack
    
    Installation:
    ```python
    handler = ErrorNotifierHandler(
        severity_threshold=logging.CRITICAL,
        discord_webhook="https://discord.com/api/webhooks/...",
    )
    logging.getLogger().addHandler(handler)
    ```
    """
    
    def __init__(
        self,
        severity_threshold: int = logging.CRITICAL,
        discord_webhook: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        project_name: str = "Crypto Trade Hub",
        environment: str = "production",
    ):
        """
        Initialize error notifier handler
        
        Args:
            severity_threshold: Minimum log level to send alerts (default: CRITICAL)
            discord_webhook: Discord webhook URL
            slack_webhook: Slack webhook URL
            project_name: Project name for alerts
            environment: Environment name (dev/staging/production)
        """
        super().__init__()
        self.severity_threshold = severity_threshold
        
        # Initialize notifier
        self.error_notifier = ErrorNotifier(
            discord_webhook_url=discord_webhook,
            slack_webhook_url=slack_webhook,
            project_name=project_name,
            environment=environment,
        )
        
        # Track recently sent alerts to prevent spam
        self.last_alerts: dict[str, float] = {}
        self.alert_cooldown_seconds = 60  # Don't send same alert more than once per minute
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Handle a log record by sending to Discord/Slack if severity matches
        """
        try:
            # Skip if below threshold
            if record.levelno < self.severity_threshold:
                return
            
            # Skip if recently sent (prevent spam)
            alert_key = f"{record.name}:{record.msg}"
            if self._is_throttled(alert_key):
                return
            
            # Map logging levels to alert severity
            severity_map = {
                logging.CRITICAL: AlertSeverity.CRITICAL,
                logging.ERROR: AlertSeverity.ERROR,
                logging.WARNING: AlertSeverity.WARNING,
                logging.INFO: AlertSeverity.INFO,
            }
            severity = severity_map.get(record.levelno, AlertSeverity.INFO)
            
            # Build alert
            alert = ErrorAlert(
                severity=severity,
                title=f"[{self.error_notifier.environment.upper()}] {record.name}",
                message=record.getMessage(),
                error_code=None,
                endpoint=record.pathname,
                stacktrace=record.exc_text or None,
                timestamp=record.asctime,
                tags={
                    "logger": record.name,
                    "level": record.levelname,
                    "function": record.funcName or "unknown",
                    "line": str(record.lineno),
                },
            )
            
            # Send alerts asynchronously
            asyncio.create_task(self._send_alert(alert, alert_key))
            
        except Exception as e:
            # Don't  let logging failures break the app
            print(f"[ErrorNotifierHandler] Error sending alert: {e}")
    
    def _is_throttled(self, alert_key: str) -> bool:
        """Check if alert was recently sent (throttling)"""
        import time
        
        now = time.time()
        if alert_key in self.last_alerts:
            if (now - self.last_alerts[alert_key]) < self.alert_cooldown_seconds:
                return True
        
        self.last_alerts[alert_key] = now
        return False
    
    async def _send_alert(self, alert: ErrorAlert, alert_key: str) -> None:
        """Send alert to Discord/Slack asynchronously"""
        try:
            # Discord
            if self.error_notifier.discord_webhook_url:
                try:
                    await self.error_notifier.send_error_alert_async(alert)
                    print(f"[✓] Alert sent to Discord: {alert.title}")
                except Exception as e:
                    print(f"[✗] Failed to send Discord alert: {e}")
            
            # Slack
            if self.error_notifier.slack_webhook_url:
                try:
                    await self.error_notifier.send_event_alert_async(
                        EventAlert(
                            severity=alert.severity,
                            title=alert.title,
                            message=alert.message,
                            details=alert.tags,
                        )
                    )
                    print(f"[✓] Alert sent to Slack: {alert.title}")
                except Exception as e:
                    print(f"[✗] Failed to send Slack alert: {e}")
        except Exception as e:
            print(f"[ErrorNotifierHandler] Error in _send_alert: {e}")


def setup_error_notifier_handler(
    logger: logging.Logger,
    severity_threshold: int = logging.CRITICAL,
) -> Optional[ErrorNotifierHandler]:
    """
    Helper function to setup error notifier handler on a logger
    
    Usage:
    ```python
    import logging
    from app.services.error_notifier_handler import setup_error_notifier_handler
    
    logger = logging.getLogger(__name__)
    setup_error_notifier_handler(logger, logging.CRITICAL)
    
    # Now CRITICAL logs automatically send Discord/Slack alerts
    logger.critical("Database connection lost - SQLite fallback active")
    ```
    """
    
    # Check if webhooks are configured
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    
    if not discord_webhook and not slack_webhook:
        print("[WARN] No Discord/Slack webhooks configured. Error notifier disabled.")
        return None
    
    # Create and attach handler
    handler = ErrorNotifierHandler(
        severity_threshold=severity_threshold,
        discord_webhook=discord_webhook,
        slack_webhook=slack_webhook,
        environment=os.getenv("APP_MODE", "production"),
    )
    
    logger.addHandler(handler)
    print(f"[✓] Error notifier handler attached to {logger.name}")
    
    return handler


# Import EventAlert for type hints
from app.services.error_notifier import EventAlert  # noqa: E402, F401
