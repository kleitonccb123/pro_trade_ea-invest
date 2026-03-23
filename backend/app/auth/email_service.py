"""
Email Service — Envio de OTP para recuperação de senha
======================================================

Configuração via variáveis de ambiente:
  SMTP_HOST    (padrão: smtp.gmail.com)
  SMTP_PORT    (padrão: 587)
  SMTP_USER    ex: seu@gmail.com
  SMTP_PASS    sua senha de app Gmail (não a senha normal)
  SMTP_FROM    (padrão: igual a SMTP_USER)

Se SMTP_USER não estiver configurado, o código OTP é apenas
registrado no log — útil para desenvolvimento.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# ── Configuração SMTP ──────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER) or "noreply@cryptotradehub.com"

EMAIL_CONFIGURED = bool(SMTP_USER and SMTP_PASS)


def _build_html(otp: str, name: str) -> str:
    """Gera o corpo HTML do email OTP."""
    digits = "".join(
        f'<span style="display:inline-block;width:44px;height:54px;line-height:54px;'
        f'text-align:center;background:#1e293b;color:#22d3ee;font-size:28px;'
        f'font-weight:700;border-radius:10px;border:1.5px solid #334155;'
        f'margin:0 4px;letter-spacing:0;">{d}</span>'
        for d in otp
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:48px 16px;">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#1a2236;border-radius:18px;overflow:hidden;
                    border:1px solid #1e293b;box-shadow:0 20px 60px rgba(0,0,0,.5);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#0ea5e9,#6366f1);
                     padding:32px 40px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#fff;letter-spacing:-0.5px;">
              🔐 CryptoTradeHub
            </div>
            <div style="color:rgba(255,255,255,.8);font-size:13px;margin-top:4px;">
              Recuperação de Senha
            </div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px;">
            <p style="color:#94a3b8;font-size:15px;margin:0 0 8px 0;">
              Olá, <strong style="color:#e2e8f0;">{name}</strong>!
            </p>
            <p style="color:#cbd5e1;font-size:15px;margin:0 0 32px 0;">
              Recebemos um pedido de recuperação de senha para a sua conta.
              Use o código abaixo para continuar:
            </p>

            <!-- OTP Box -->
            <div style="text-align:center;margin:0 0 32px 0;">
              {digits}
            </div>

            <div style="background:#0f172a;border-radius:10px;padding:16px 20px;
                        border:1px solid #1e293b;margin-bottom:28px;">
              <p style="color:#94a3b8;font-size:13px;margin:0;">
                ⏱️ <strong style="color:#e2e8f0;">Válido por 10 minutos.</strong>
                Não compartilhe este código com ninguém.
              </p>
            </div>

            <p style="color:#64748b;font-size:13px;margin:0;">
              Se você não solicitou a recuperação de senha, ignore este email.
              Sua senha não será alterada.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 40px;border-top:1px solid #1e293b;text-align:center;">
            <p style="color:#475569;font-size:12px;margin:0;">
              © {2026} CryptoTradeHub · Este é um email automático
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_otp_email(to_email: str, otp: str, name: str = "usuário") -> bool:
    """
    Envia o email com o código OTP.

    Returns:
        True  → email enviado (ou logado em modo dev)
        False → falha no envio
    """
    if not EMAIL_CONFIGURED:
        # Modo desenvolvimento: apenas loga
        logger.warning(
            "⚠️  SMTP não configurado — modo DEV. "
            f"OTP para {to_email}: [{otp}]"
        )
        print(f"\n{'='*60}")
        print(f"  📧  EMAIL OTP (modo dev — sem SMTP configurado)")
        print(f"  Para:  {to_email}")
        print(f"  Nome:  {name}")
        print(f"  OTP:   {otp}")
        print(f"{'='*60}\n")
        return True  # Simula sucesso para desenvolvimento

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🔐 Código de recuperação de senha — CryptoTradeHub"
        msg["From"] = f"CryptoTradeHub <{SMTP_FROM}>"
        msg["To"] = to_email

        # Parte texto simples (fallback)
        text_body = (
            f"Olá, {name}!\n\n"
            f"Seu código de recuperação de senha: {otp}\n\n"
            "Válido por 10 minutos.\n\n"
            "Se você não solicitou, ignore este email."
        )
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(_build_html(otp, name), "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())

        logger.info(f"✅ OTP email enviado para {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("❌ Falha de autenticação SMTP. Verifique SMTP_USER e SMTP_PASS.")
        return False
    except smtplib.SMTPException as exc:
        logger.error(f"❌ Erro SMTP ao enviar para {to_email}: {exc}")
        return False
    except Exception as exc:
        logger.error(f"❌ Erro inesperado ao enviar email: {exc}")
        return False


# ---------------------------------------------------------------------------
# Email Verification (P1-05)
# Uses Redis when available, falls back to in-memory. Tokens expire in 24 h.
# ---------------------------------------------------------------------------

import secrets as _secrets
import time as _time

_verification_store: dict = {}  # {token: {"email": str, "expires": float}}
_VERIFICATION_TTL = 24 * 3600   # 24 hours


async def create_verification_token(email: str) -> str:
    """Generate and store a 32-byte URL-safe verification token."""
    token = _secrets.token_urlsafe(32)
    expires = _time.time() + _VERIFICATION_TTL

    try:
        from app.core.config import settings as _cfg
        if _cfg.redis_url:
            import redis.asyncio as _aioredis
            _r = _aioredis.from_url(_cfg.redis_url, decode_responses=True)
            await _r.setex(f"verify_email:{token}", _VERIFICATION_TTL, email)
            await _r.aclose()
            return token
    except Exception:
        pass

    # In-memory fallback
    _verification_store[token] = {"email": email, "expires": expires}
    return token


async def consume_verification_token(token: str) -> str | None:
    """
    Validate the token and return the associated email (or None if invalid/expired).
    Deletes the token after one successful use.
    """
    try:
        from app.core.config import settings as _cfg
        if _cfg.redis_url:
            import redis.asyncio as _aioredis
            _r = _aioredis.from_url(_cfg.redis_url, decode_responses=True)
            email = await _r.get(f"verify_email:{token}")
            if email:
                await _r.delete(f"verify_email:{token}")
            await _r.aclose()
            return email or None
    except Exception:
        pass

    # In-memory fallback
    entry = _verification_store.pop(token, None)
    if not entry:
        return None
    if _time.time() > entry["expires"]:
        return None
    return entry["email"]


async def send_verification_email(to_email: str, token: str, name: str = "usuário") -> bool:
    """Send the email-verification link. Logs the link in dev mode."""
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:8081")
    verify_url = f"{frontend_url}/verify-email?token={token}"

    if not EMAIL_CONFIGURED:
        logger.warning(
            "⚠️  SMTP não configurado — modo DEV. "
            f"Link de verificação para {to_email}: {verify_url}"
        )
        print(f"\n{'='*60}")
        print(f"  📧  EMAIL VERIFICATION (modo dev — sem SMTP configurado)")
        print(f"  Para:  {to_email}")
        print(f"  Link:  {verify_url}")
        print(f"{'='*60}\n")
        return True

    try:
        body_txt = (
            f"Olá, {name}!\n\n"
            f"Confirme seu email clicando no link abaixo:\n{verify_url}\n\n"
            "O link expira em 24 horas.\n\n"
            "Se você não criou esta conta, ignore este email."
        )
        body_html = f"""
        <p>Olá, <strong>{name}</strong>!</p>
        <p>Clique no botão abaixo para verificar seu email:</p>
        <p><a href="{verify_url}" style="padding:10px 20px;background:#0ea5e9;
           color:#fff;text-decoration:none;border-radius:6px;">Verificar Email</a></p>
        <p style="color:#888;font-size:12px;">Link válido por 24 horas.</p>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "✅ Verifique seu email — CryptoTradeHub"
        msg["From"] = f"CryptoTradeHub <{SMTP_FROM}>"
        msg["To"] = to_email
        msg.attach(MIMEText(body_txt, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, [to_email], msg.as_string())

        logger.info(f"✅ Email de verificação enviado para {to_email}")
        return True

    except Exception as exc:
        logger.error(f"❌ Erro ao enviar email de verificação para {to_email}: {exc}")
        return False
