"""
Forgot Password Router
======================
Endpoints para recuperação de senha via OTP enviado por email.

Fluxo:
  1. POST /api/auth/forgot-password   → gera OTP, envia email
  2. POST /api/auth/verify-otp        → valida código (sem consumir)
  3. POST /api/auth/reset-password    → valida código + atualiza senha

OTPs ficam em memória com TTL de 10 minutos.
"""

from __future__ import annotations

import logging
import random
import string
import time
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.auth.email_service import send_otp_email
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["🔑 Auth - Password Reset"])

# ─────────────────────────────────────────────────────────────────────────────
# Store em memória: { email → {otp, expires_at, name, user_id, provider, backend} }
# ─────────────────────────────────────────────────────────────────────────────

OTP_TTL_SECONDS = 600  # 10 minutos
OTP_STORE: Dict[str, Dict[str, Any]] = {}


def _gen_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def _cleanup_expired():
    now = time.time()
    expired = [e for e, v in OTP_STORE.items() if v["expires_at"] < now]
    for e in expired:
        del OTP_STORE[e]


def _get_otp_entry(email: str) -> Dict[str, Any] | None:
    entry = OTP_STORE.get(email.lower())
    if not entry:
        return None
    if entry["expires_at"] < time.time():
        del OTP_STORE[email.lower()]
        return None
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de banco (SQLite ou MongoDB)
# ─────────────────────────────────────────────────────────────────────────────

async def _find_user(email: str):
    """Busca usuário primeiro no SQLite, depois no MongoDB."""
    email = email.lower().strip()

    # 1 — SQLite (usuários locais / Google OAuth locais)
    try:
        from app.core.local_db_manager import get_local_db
        local_db = get_local_db()
        user = await local_db.find_user_by_email(email)
        if user:
            return user, "sqlite"
    except Exception as exc:
        logger.debug(f"SQLite lookup failed: {exc}")

    # 2 — MongoDB
    try:
        from app.core.database import get_db
        db = get_db()
        user = await db.users.find_one({"email": email})
        if user:
            return user, "mongo"
    except Exception as exc:
        logger.debug(f"MongoDB lookup failed: {exc}")

    return None, None


async def _update_password(email: str, backend: str, new_hash: str) -> bool:
    """Atualiza hashed_password no backend correto."""
    email = email.lower().strip()

    if backend == "sqlite":
        try:
            from app.core.local_db_manager import get_local_db
            local_db = get_local_db()
            user = await local_db.find_user_by_email(email)
            if not user:
                return False
            user_id = user.get("_id") or user.get("id")
            await local_db.update_user(str(user_id), {"hashed_password": new_hash})
            return True
        except Exception as exc:
            logger.error(f"Erro ao atualizar senha no SQLite: {exc}")
            return False

    if backend == "mongo":
        try:
            from app.core.database import get_db
            db = get_db()
            result = await db.users.update_one(
                {"email": email},
                {"$set": {"hashed_password": new_hash, "password_hash": new_hash}},
            )
            return result.modified_count > 0
        except Exception as exc:
            logger.error(f"Erro ao atualizar senha no MongoDB: {exc}")
            return False

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """
    Passo 1 — Solicitar código OTP.

    - Verifica se o email existe.
    - Garante que o usuário não seja Google-Only.
    - Gera um OTP de 6 dígitos, armazena com TTL de 10 min.
    - Envia o código por email.
    """
    _cleanup_expired()
    email = req.email.lower().strip()

    user, backend = await _find_user(email)

    # Resposta genérica para não vazar se email existe ou não
    GENERIC_OK = JSONResponse(
        content={
            "success": True,
            "message": "Se este email estiver cadastrado, você receberá um código em breve.",
        }
    )

    if not user:
        logger.info(f"[ForgotPassword] Email não encontrado: {email}")
        return GENERIC_OK

    # Usuários somente-Google não têm senha para redefinir
    provider = user.get("auth_provider", "local")
    has_password = bool(user.get("hashed_password", "").strip())
    if provider == "google" and not has_password:
        logger.info(f"[ForgotPassword] Usuário Google-only: {email}")
        # Retornamos mensagem mais amigável (não vaza se existe ou não)
        return JSONResponse(
            content={
                "success": False,
                "google_account": True,
                "message": (
                    "Esta conta usa Login com Google. "
                    "Não é possível redefinir senha por este fluxo — "
                    "utilize o botão 'Fazer Login com o Google'."
                ),
            }
        )

    name = user.get("full_name") or user.get("name") or "usuário"
    otp = _gen_otp(6)
    OTP_STORE[email] = {
        "otp": otp,
        "expires_at": time.time() + OTP_TTL_SECONDS,
        "name": name,
        "backend": backend,
    }

    sent = await send_otp_email(to_email=email, otp=otp, name=name)
    if not sent:
        # Remove OTP se o email falhou
        OTP_STORE.pop(email, None)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enviar o email. Tente novamente em instantes.",
        )

    logger.info(f"[ForgotPassword] OTP enviado para {email}")
    return GENERIC_OK


@router.post("/verify-otp")
async def verify_otp(req: VerifyOTPRequest):
    """
    Passo 2 — Validar código OTP.
    Não consome o código (ele será consumido no reset-password).
    """
    email = req.email.lower().strip()
    entry = _get_otp_entry(email)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido ou expirado. Solicite um novo código.",
        )

    if entry["otp"] != req.otp.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código incorreto. Verifique e tente novamente.",
        )

    remaining = int(entry["expires_at"] - time.time())
    return {
        "success": True,
        "message": "Código válido.",
        "remaining_seconds": max(0, remaining),
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """
    Passo 3 — Redefinir a senha.
    Valida OTP, atualiza a senha no banco e remove o OTP.
    """
    email = req.email.lower().strip()
    entry = _get_otp_entry(email)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código inválido ou expirado. Solicite um novo código.",
        )

    if entry["otp"] != req.otp.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código incorreto.",
        )

    # Validação mínima de senha
    if len(req.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A nova senha deve ter pelo menos 6 caracteres.",
        )

    new_hash = get_password_hash(req.new_password)
    updated = await _update_password(email, entry["backend"], new_hash)

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível atualizar a senha. Tente novamente.",
        )

    # Consome o OTP
    OTP_STORE.pop(email, None)
    logger.info(f"[ResetPassword] ✅ Senha redefinida para {email}")

    return {
        "success": True,
        "message": "Senha redefinida com sucesso! Você já pode fazer login.",
    }
