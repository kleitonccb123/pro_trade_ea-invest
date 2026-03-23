"""
Notification Service - L?gica de neg?cio do sistema de notifica??es (Motor/MongoDB)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from bson import ObjectId

from app.core.database import get_db
from app.notifications.models import (
    NotificationType,
    NotificationPriority,
    PriceAlertCondition,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Servi?o principal de notifica??es com Motor/MongoDB"""
    
    # ============== NOTIFICATIONS ==============
    
    async def create_notification(
        self,
        user_id: int,
        type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[dict] = None
    ) -> dict:
        """Cria uma nova notifica??o e envia pelos canais configurados"""
        
        db = get_db()
        try:
            # Verificar prefer?ncias do usu?rio
            prefs = await self.get_preferences(user_id)
            
            # Verificar se este tipo est? habilitado
            if not self._is_type_enabled(type, prefs):
                logger.debug(f"Notification type {type} disabled for user {user_id}")
                return None
            
            # Verificar hor?rio de sil?ncio
            if self._is_quiet_hours(prefs):
                logger.debug(f"Quiet hours active for user {user_id}")
                # Ainda cria a notifica??o, mas n?o envia push/email
                send_push = False
                send_email = False
            else:
                send_push = prefs.get('push_enabled', True) if prefs else True
                send_email = prefs.get('email_enabled', False) if prefs else False
            
            # Criar notifica??o
            notification = {
                "user_id": user_id,
                "type": type.value if hasattr(type, 'value') else str(type),
                "priority": priority.value if hasattr(priority, 'value') else str(priority),
                "title": title,
                "message": message,
                "data": data or {},
                "sent_push": send_push,
                "sent_email": send_email,
                "is_read": False,
                "created_at": datetime.utcnow(),
                "read_at": None
            }
            
            result = await db['notifications'].insert_one(notification)
            notification['_id'] = result.inserted_id
            
            # TODO: Enviar push notification real aqui
            if send_push:
                await self._send_push_notification(user_id, notification, prefs)
            
            # TODO: Enviar email aqui
            if send_email:
                await self._send_email_notification(user_id, notification, prefs)
            
            logger.info(f"Notification created: {result.inserted_id} for user {user_id}")
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None
    
    async def get_notifications(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False
    ) -> tuple[List[dict], int, int]:
        """Retorna notifica??es do usu?rio com contagem"""
        
        db = get_db()
        try:
            # Filtro base
            filter_query = {"user_id": user_id}
            
            if unread_only:
                filter_query["is_read"] = False
            
            # Total
            total = await db['notifications'].count_documents(filter_query)
            
            # N?o lidas
            unread_count = await db['notifications'].count_documents({
                "user_id": user_id,
                "is_read": False
            })
            
            # Buscar com pagina??o
            notifications = await db['notifications'].find(filter_query)\
                .sort("created_at", -1)\
                .skip(offset)\
                .limit(limit)\
                .to_list(length=limit)
            
            return notifications, total, unread_count
            
        except Exception as e:
            logger.error(f"Error getting notifications: {e}")
            return [], 0, 0
    
    async def mark_as_read(
        self,
        user_id: int,
        notification_ids: List[str]
    ) -> int:
        """Marca notifica??es como lidas"""
        
        db = get_db()
        try:
            # Converter string IDs para ObjectId
            oid_list = [ObjectId(nid) if isinstance(nid, str) else nid for nid in notification_ids]
            
            result = await db['notifications'].update_many(
                {
                    "user_id": user_id,
                    "_id": {"$in": oid_list},
                    "is_read": False
                },
                {
                    "$set": {
                        "is_read": True,
                        "read_at": datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Error marking notifications as read: {e}")
            return 0
    
    async def mark_all_as_read(self, user_id: int) -> int:
        """Marca todas as notifica??es como lidas"""
        
        db = get_db()
        try:
            result = await db['notifications'].update_many(
                {
                    "user_id": user_id,
                    "is_read": False
                },
                {
                    "$set": {
                        "is_read": True,
                        "read_at": datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return 0
    
    async def delete_notification(
        self,
        user_id: int,
        notification_id: str
    ) -> bool:
        """Deleta uma notifica??o"""
        
        db = get_db()
        try:
            oid = ObjectId(notification_id) if isinstance(notification_id, str) else notification_id
            
            result = await db['notifications'].delete_one({
                "user_id": user_id,
                "_id": oid
            })
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return False
    
    async def clear_old_notifications(self, days: int = 30) -> int:
        """Remove notifica??es antigas"""
        
        db = get_db()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            result = await db['notifications'].delete_many({
                "created_at": {"$lt": cutoff}
            })
            
            logger.info(f"Cleared {result.deleted_count} old notifications")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Error clearing old notifications: {e}")
            return 0
    
    # ============== PREFERENCES ==============
    
    async def get_preferences(
        self,
        user_id: int
    ) -> Optional[dict]:
        """Retorna prefer?ncias do usu?rio"""
        
        db = get_db()
        try:
            prefs = await db['notification_preferences'].find_one({
                "user_id": user_id
            })
            return prefs
            
        except Exception as e:
            logger.error(f"Error getting preferences: {e}")
            return None
    
    async def get_or_create_preferences(
        self,
        user_id: int
    ) -> dict:
        """Retorna ou cria prefer?ncias padr?o"""
        
        db = get_db()
        try:
            prefs = await self.get_preferences(user_id)
            
            if not prefs:
                prefs = {
                    "user_id": user_id,
                    "push_enabled": True,
                    "email_enabled": False,
                    "price_alerts_enabled": True,
                    "bot_trades_enabled": True,
                    "bot_status_enabled": True,
                    "reports_enabled": True,
                    "system_updates_enabled": False,
                    "daily_summary_enabled": True,
                    "weekly_summary_enabled": True,
                    "quiet_hours_enabled": False,
                    "quiet_hours_start": "22:00",
                    "quiet_hours_end": "08:00",
                    "push_subscription": None,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                result = await db['notification_preferences'].insert_one(prefs)
                prefs['_id'] = result.inserted_id
                logger.info(f"Created default preferences for user {user_id}")
            
            return prefs
            
        except Exception as e:
            logger.error(f"Error getting/creating preferences: {e}")
            return {}
    
    async def update_preferences(
        self,
        user_id: int,
        updates: dict
    ) -> dict:
        """Atualiza prefer?ncias do usu?rio"""
        
        db = get_db()
        try:
            prefs = await self.get_or_create_preferences(user_id)
            
            # Preparar update com timestamp
            update_data = updates.copy()
            update_data['updated_at'] = datetime.utcnow()
            
            result = await db['notification_preferences'].update_one(
                {"user_id": user_id},
                {"$set": update_data}
            )
            
            # Retornar dados atualizados
            return await self.get_preferences(user_id)
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return {}
    
    async def register_push_subscription(
        self,
        user_id: int,
        subscription: dict
    ) -> bool:
        """Registra subscription para push notifications"""
        
        db = get_db()
        try:
            result = await db['notification_preferences'].update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "push_subscription": subscription,
                        "push_enabled": True,
                        "updated_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            
            logger.info(f"Push subscription registered for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering push subscription: {e}")
            return False
    
    # ============== PRICE ALERTS ==============
    
    async def create_price_alert(
        self,
        user_id: int,
        symbol: str,
        condition: str,
        target_price: float,
        percent_change: Optional[float] = None,
        repeat: bool = False,
        note: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        current_price: Optional[float] = None
    ) -> dict:
        """Cria um novo alerta de pre?o"""
        
        db = get_db()
        try:
            alert = {
                "user_id": user_id,
                "symbol": symbol.upper(),
                "condition": condition,
                "target_price": target_price,
                "percent_change": percent_change,
                "base_price": current_price,
                "repeat": repeat,
                "note": note,
                "expires_at": expires_at,
                "is_active": True,
                "is_triggered": False,
                "triggered_at": None,
                "triggered_price": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = await db['price_alerts'].insert_one(alert)
            alert['_id'] = result.inserted_id
            
            logger.info(f"Price alert created: {result.inserted_id} for {symbol} @ {target_price}")
            return alert
            
        except Exception as e:
            logger.error(f"Error creating price alert: {e}")
            return None
    
    async def get_price_alerts(
        self,
        user_id: int,
        active_only: bool = True
    ) -> List[dict]:
        """Retorna alertas de pre?o do usu?rio"""
        
        db = get_db()
        try:
            filter_query = {"user_id": user_id}
            
            if active_only:
                filter_query["is_active"] = True
            
            alerts = await db['price_alerts'].find(filter_query)\
                .sort("created_at", -1)\
                .to_list(length=None)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting price alerts: {e}")
            return []
    
    async def update_price_alert(
        self,
        user_id: int,
        alert_id: str,
        updates: dict
    ) -> Optional[dict]:
        """Atualiza um alerta de pre?o"""
        
        db = get_db()
        try:
            oid = ObjectId(alert_id) if isinstance(alert_id, str) else alert_id
            
            update_data = updates.copy()
            update_data['updated_at'] = datetime.utcnow()
            
            result = await db['price_alerts'].find_one_and_update(
                {
                    "user_id": user_id,
                    "_id": oid
                },
                {"$set": update_data},
                return_document=True
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error updating price alert: {e}")
            return None
    
    async def delete_price_alert(
        self,
        user_id: int,
        alert_id: str
    ) -> bool:
        """Deleta um alerta de pre?o"""
        
        db = get_db()
        try:
            oid = ObjectId(alert_id) if isinstance(alert_id, str) else alert_id
            
            result = await db['price_alerts'].delete_one({
                "user_id": user_id,
                "_id": oid
            })
            
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error deleting price alert: {e}")
            return False
    
    async def check_price_alerts(self, current_prices: dict[str, float]) -> List[dict]:
        """Verifica todos os alertas ativos contra pre?os atuais"""
        
        db = get_db()
        triggered_alerts = []
        now = datetime.utcnow()
        
        try:
            # Buscar todos alertas ativos
            alerts = await db['price_alerts'].find({
                "is_active": True,
                "is_triggered": False
            }).to_list(None)
            
            for alert in alerts:
                # Verificar expira??o
                if alert.get('expires_at') and alert['expires_at'] < now:
                    await db['price_alerts'].update_one(
                        {"_id": alert['_id']},
                        {"$set": {"is_active": False}}
                    )
                    continue
                
                symbol = alert.get('symbol')
                if symbol not in current_prices:
                    continue
                
                current_price = current_prices[symbol]
                triggered = False
                
                # Verificar condi??o
                condition = alert.get('condition')
                if condition == 'above':
                    triggered = current_price >= alert.get('target_price', 0)
                elif condition == 'below':
                    triggered = current_price <= alert.get('target_price', 0)
                elif condition == 'change_percent':
                    if alert.get('base_price') and alert.get('percent_change'):
                        change = ((current_price - alert['base_price']) / alert['base_price']) * 100
                        triggered = abs(change) >= abs(alert['percent_change'])
                
                if triggered:
                    update_data = {
                        "is_triggered": True,
                        "triggered_at": now,
                        "triggered_price": current_price
                    }
                    
                    if not alert.get('repeat', False):
                        update_data["is_active"] = False
                    else:
                        # Reset para alertar novamente
                        update_data["is_triggered"] = False
                        update_data["base_price"] = current_price
                    
                    await db['price_alerts'].update_one(
                        {"_id": alert['_id']},
                        {"$set": update_data}
                    )
                    
                    triggered_alerts.append(alert)
                    
                    # Criar notifica??o
                    await self.create_notification(
                        user_id=alert['user_id'],
                        type=NotificationType.PRICE_ALERT,
                        title=f"? Alerta de Pre?o: {symbol}",
                        message=self._format_price_alert_message(alert, current_price),
                        priority=NotificationPriority.HIGH,
                        data={
                            "alert_id": str(alert['_id']),
                            "symbol": symbol,
                            "target_price": alert.get('target_price'),
                            "current_price": current_price,
                            "condition": condition
                        }
                    )
            
            if triggered_alerts:
                logger.info(f"Triggered {len(triggered_alerts)} price alerts")
            
        except Exception as e:
            logger.error(f"Error checking price alerts: {e}")
        
        return triggered_alerts
    
    # ============== HELPER METHODS ==============
    
    def _is_type_enabled(self, type: NotificationType, prefs: Optional[dict]) -> bool:
        """Verifica se um tipo de notifica??o est? habilitado"""
        if not prefs:
            return True  # Default: habilitado
        
        type_str = type.value if hasattr(type, 'value') else str(type)
        
        type_mapping = {
            'price_alert': prefs.get('price_alerts_enabled', True),
            'bot_trade': prefs.get('bot_trades_enabled', True),
            'bot_status': prefs.get('bot_status_enabled', True),
            'report': prefs.get('reports_enabled', True),
            'system': prefs.get('system_updates_enabled', False),
            'summary': prefs.get('daily_summary_enabled', True),
        }
        
        # Buscar pela chave ou retornar True por padr?o
        for key, enabled in type_mapping.items():
            if key in type_str.lower():
                return enabled
        
        return True
    
    def _is_quiet_hours(self, prefs: Optional[dict]) -> bool:
        """Verifica se est? no hor?rio de sil?ncio"""
        if not prefs or not prefs.get('quiet_hours_enabled', False):
            return False
        
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            start = prefs.get('quiet_hours_start', '22:00')
            end = prefs.get('quiet_hours_end', '08:00')
            
            # Lidar com per?odo que cruza meia-noite
            if start <= end:
                return start <= current_time <= end
            else:
                return current_time >= start or current_time <= end
        except Exception:
            return False
    
    def _format_price_alert_message(self, alert: dict, current_price: float) -> str:
        """Formata mensagem de alerta de pre?o"""
        condition_text = {
            'above': "atingiu ou ultrapassou",
            'below': "caiu para ou abaixo de",
            'crosses_up': "cruzou para cima de",
            'crosses_down': "cruzou para baixo de",
            'change_percent': f"variou {alert.get('percent_change')}%",
        }
        
        condition = alert.get('condition', 'above')
        action = condition_text.get(condition, "atingiu")
        msg = f"{alert.get('symbol')} {action} ${alert.get('target_price', 0):,.2f}"
        msg += f"\nPre?o atual: ${current_price:,.2f}"
        
        if alert.get('note'):
            msg += f"\nNota: {alert['note']}"
        
        return msg
    
    async def _send_push_notification(
        self,
        user_id: int,
        notification: dict,
        prefs: Optional[dict]
    ):
        """Envia push notification via Web Push API (pywebpush).

        If push delivery fails (expired subscription, missing config, etc.),
        falls back to email notification automatically.
        """
        subscription_info = (prefs or {}).get("push_subscription")
        if not subscription_info or not subscription_info.get("endpoint"):
            logger.debug("No push subscription for user %s — falling back to email", user_id)
            await self._send_email_notification(user_id, notification, prefs)
            return

        from app.core.config import settings as app_settings

        if not app_settings.vapid_private_key or not app_settings.vapid_claims_email:
            logger.warning("VAPID keys not configured — skipping push for user %s", user_id)
            await self._send_email_notification(user_id, notification, prefs)
            return

        try:
            import json
            from pywebpush import webpush, WebPushException

            payload = json.dumps({
                "title": notification.get("title", "CryptoTradeHub"),
                "body": notification.get("message", ""),
                "icon": "/favicon.ico",
                "badge": "/favicon.ico",
                "tag": notification.get("type", "general"),
                "data": {
                    "url": "/",
                    "notification_id": str(notification.get("_id", "")),
                    **(notification.get("data") or {}),
                },
            })

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=app_settings.vapid_private_key,
                vapid_claims={"sub": app_settings.vapid_claims_email},
            )

            logger.info("Push notification sent to user %s", user_id)

        except Exception as exc:
            exc_str = str(exc)
            logger.warning("Push failed for user %s: %s — falling back to email", user_id, exc_str)

            # If subscription expired / invalid, clean it up
            if "410" in exc_str or "404" in exc_str:
                try:
                    db = get_db()
                    await db["notification_preferences"].update_one(
                        {"user_id": user_id},
                        {"$set": {"push_subscription": None, "push_enabled": False}},
                    )
                    logger.info("Removed stale push subscription for user %s", user_id)
                except Exception:
                    pass

            # Fallback to email
            await self._send_email_notification(user_id, notification, prefs)
    
    async def _send_email_notification(
        self,
        user_id: int,
        notification: dict,
        prefs: Optional[dict]
    ):
        """Envia notificação por email usando o SMTP configurado."""
        try:
            db = get_db()
            # Look up user email
            from bson import ObjectId
            user_doc = None
            try:
                user_doc = await db.users.find_one({"_id": ObjectId(str(user_id))})
            except Exception:
                pass
            if not user_doc:
                # Try string lookup
                user_doc = await db.users.find_one({"_id": str(user_id)})

            if not user_doc or not user_doc.get("email"):
                logger.debug("No email for user %s, skipping email notification", user_id)
                return

            from app.auth.email_service import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, EMAIL_CONFIGURED
            if not EMAIL_CONFIGURED:
                logger.debug(
                    "[NotifEmail] SMTP not configured. Would email %s: %s",
                    user_doc["email"], notification.get("title"),
                )
                return

            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            title = notification.get("title", "Notificação")
            message = notification.get("message", "")
            notif_type = notification.get("type", "system")

            html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:48px 16px;">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#1a2236;border-radius:18px;overflow:hidden;
                    border:1px solid #1e293b;">
        <tr>
          <td style="background:linear-gradient(135deg,#0ea5e9,#6366f1);
                     padding:24px 32px;text-align:center;">
            <div style="font-size:22px;font-weight:700;color:#fff;">
              🔔 CryptoTradeHub
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <p style="color:#e2e8f0;font-size:18px;font-weight:600;margin:0 0 12px;">
              {title}
            </p>
            <p style="color:#94a3b8;font-size:14px;margin:0 0 24px;line-height:1.6;">
              {message}
            </p>
            <div style="background:#0f172a;border-radius:8px;padding:12px 16px;
                        border:1px solid #1e293b;">
              <p style="color:#64748b;font-size:12px;margin:0;">
                Tipo: {notif_type} · Esta notificação foi enviada automaticamente.
              </p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 32px;border-top:1px solid #1e293b;text-align:center;">
            <p style="color:#475569;font-size:11px;margin:0;">
              © 2026 CryptoTradeHub · Gerencie suas preferências em Configurações
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🔔 {title} — CryptoTradeHub"
            msg["From"] = f"CryptoTradeHub <{SMTP_FROM}>"
            msg["To"] = user_doc["email"]

            msg.attach(MIMEText(f"{title}\n\n{message}", "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)

            logger.info("Email notification sent to %s: %s", user_doc["email"][:3] + "***", title)

        except Exception as exc:
            logger.warning("Failed to send email notification to user %s: %s", user_id, exc)


# Singleton
notification_service = NotificationService()
