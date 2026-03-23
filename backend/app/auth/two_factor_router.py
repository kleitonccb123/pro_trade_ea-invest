"""
2FA API Router - Endpoints para autentica??o de dois fatores

Endpoints:
- POST /api/auth/2fa/setup - Iniciar configura??o
- POST /api/auth/2fa/confirm - Confirmar com c?digo
- POST /api/auth/2fa/verify - Verificar c?digo
- POST /api/auth/2fa/disable - Desativar
- GET /api/auth/2fa/status - Status do 2FA
- POST /api/auth/2fa/backup-codes - Regenerar backup codes
- GET /api/auth/sessions - Listar sess?es ativas
- DELETE /api/auth/sessions/{id} - Revogar sess?o

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.auth.two_factor import two_factor_service, session_manager, TwoFactorSetup

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["2FA"])


# ==================== SCHEMAS ====================

class Setup2FAResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: List[str]
    message: str


class Verify2FARequest(BaseModel):
    code: str


class Verify2FAResponse(BaseModel):
    success: bool
    message: str


class Status2FAResponse(BaseModel):
    enabled: bool
    setup_started: bool
    backup_codes_remaining: Optional[int] = None
    last_verification: Optional[str] = None


class BackupCodesResponse(BaseModel):
    success: bool
    backup_codes: List[str]


class SessionResponse(BaseModel):
    session_id: str
    device_info: dict
    ip_address: Optional[str]
    created_at: str
    last_activity: str


class SessionsListResponse(BaseModel):
    sessions: List[dict]
    total: int


# ==================== 2FA ENDPOINTS ====================

@router.post("/2fa/setup", response_model=Setup2FAResponse)
async def setup_2fa(current_user: dict = Depends(get_current_user)):
    """
    Inicia configura??o de 2FA.
    
    Retorna:
    - secret: Para configura??o manual
    - provisioning_uri: Para gerar QR code
    - backup_codes: C?digos de recupera??o (salvar em local seguro)
    """
    try:
        user_id = str(current_user["_id"])
        email = current_user.get("email", "user")
        
        setup = await two_factor_service.setup_2fa(user_id, email)
        
        return Setup2FAResponse(
            secret=setup.secret,
            provisioning_uri=setup.provisioning_uri,
            backup_codes=setup.backup_codes,
            message="Escaneie o QR code com seu app de autentica??o e confirme com um c?digo"
        )
    except Exception as e:
        logger.error(f"? Erro ao configurar 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/2fa/confirm", response_model=Verify2FAResponse)
async def confirm_2fa(
    request: Verify2FARequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Confirma configura??o de 2FA verificando um c?digo.
    
    Deve ser chamado ap?s escanear o QR code.
    """
    try:
        user_id = str(current_user["_id"])
        
        success = await two_factor_service.confirm_setup(user_id, request.code)
        
        if success:
            # Invalidate all other sessions for security
            try:
                await session_manager.revoke_all_sessions(user_id, except_session=None)
                logger.info(f"Sessions invalidated after 2FA enable for user {user_id}")
            except Exception:
                pass  # Non-critical — best effort
            return Verify2FAResponse(
                success=True,
                message="2FA ativado com sucesso! Guarde seus backup codes em local seguro."
            )
        else:
            return Verify2FAResponse(
                success=False,
                message="C?digo inv?lido. Verifique se o hor?rio do seu dispositivo est? correto."
            )
    except Exception as e:
        logger.error(f"? Erro ao confirmar 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/2fa/verify", response_model=Verify2FAResponse)
async def verify_2fa(
    request: Verify2FARequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Verifica um c?digo 2FA.
    
    Usado para opera??es que requerem 2FA (saques, altera??es de seguran?a, etc.)
    """
    try:
        user_id = str(current_user["_id"])
        
        success, message = await two_factor_service.verify(user_id, request.code)
        
        return Verify2FAResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"? Erro ao verificar 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/2fa/disable", response_model=Verify2FAResponse)
async def disable_2fa(
    request: Verify2FARequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Desativa 2FA (requer verifica??o com c?digo atual).
    """
    try:
        user_id = str(current_user["_id"])
        
        success, message = await two_factor_service.disable_2fa(user_id, request.code)
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        # Invalidate all other sessions for security
        try:
            await session_manager.revoke_all_sessions(user_id, except_session=None)
            logger.info(f"Sessions invalidated after 2FA disable for user {user_id}")
        except Exception:
            pass  # Non-critical — best effort
        
        return Verify2FAResponse(success=True, message=message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao desativar 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/2fa/status", response_model=Status2FAResponse)
async def get_2fa_status(current_user: dict = Depends(get_current_user)):
    """
    Retorna status do 2FA para o usu?rio atual.
    """
    try:
        user_id = str(current_user["_id"])
        
        status = await two_factor_service.get_2fa_status(user_id)
        
        return Status2FAResponse(
            enabled=status["enabled"],
            setup_started=status["setup_started"],
            backup_codes_remaining=status.get("backup_codes_remaining"),
            last_verification=status.get("last_verification").isoformat() if status.get("last_verification") else None
        )
    except Exception as e:
        logger.error(f"? Erro ao obter status 2FA: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/2fa/backup-codes", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    request: Verify2FARequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Regenera backup codes (invalida os anteriores).
    
    Requer verifica??o com c?digo 2FA atual.
    """
    try:
        user_id = str(current_user["_id"])
        
        success, codes = await two_factor_service.regenerate_backup_codes(user_id, request.code)
        
        if not success:
            raise HTTPException(status_code=400, detail="C?digo inv?lido")
        
        return BackupCodesResponse(success=True, backup_codes=codes)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao regenerar backup codes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SESSION ENDPOINTS ====================

@router.get("/sessions", response_model=SessionsListResponse)
async def list_sessions(current_user: dict = Depends(get_current_user)):
    """
    Lista sess?es ativas do usu?rio.
    """
    try:
        user_id = str(current_user["_id"])
        
        sessions = await session_manager.get_active_sessions(user_id)
        
        return SessionsListResponse(
            sessions=sessions,
            total=len(sessions)
        )
    except Exception as e:
        logger.error(f"? Erro ao listar sess?es: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Revoga uma sess?o espec?fica (faz logout do dispositivo).
    """
    try:
        user_id = str(current_user["_id"])
        
        success = await session_manager.revoke_session(user_id, session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Sess?o n?o encontrada")
        
        return {"success": True, "message": "Sess?o revogada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao revogar sess?o: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/revoke-all")
async def revoke_all_sessions(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Revoga todas as outras sess?es (mant?m a atual).
    """
    try:
        user_id = str(current_user["_id"])
        
        # Obter session_id atual do header ou cookie
        current_session = request.headers.get("X-Session-ID")
        
        count = await session_manager.revoke_all_sessions(user_id, except_session=current_session)
        
        return {
            "success": True,
            "message": f"{count} sess?es revogadas",
            "revoked_count": count
        }
    except Exception as e:
        logger.error(f"? Erro ao revogar sess?es: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 2FA LOGIN COMPLETION ====================

class Complete2FARequest(BaseModel):
    pending_token: str
    code: str


@router.post("/2fa/complete")
async def complete_2fa_login(request: Complete2FARequest):
    """
    Completes a login that requires 2FA verification.

    After a successful password login, if 2FA is enabled the login endpoint
    returns ``requires_2fa=True`` along with a short-lived ``pending_token``
    (scope="2fa_pending", TTL=5 min).  This endpoint accepts that token plus
    the TOTP code and, if valid, issues the full access + refresh token pair.
    """
    from app.auth import service as auth_service
    from app.auth.router import _set_refresh_cookie, _IS_PROD
    from app.middleware.csrf import set_csrf_cookie
    from jose import JWTError

    try:
        payload = auth_service.decode_token(request.pending_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token pendente inválido ou expirado")

    if payload.get("scope") != "2fa_pending":
        raise HTTPException(status_code=401, detail="Token não é um token 2FA pendente")

    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token inválido: sub ausente")

    ok, msg = await two_factor_service.verify(user_id, request.code)
    if not ok:
        raise HTTPException(status_code=401, detail=msg or "Código 2FA inválido")

    # Issue full tokens
    access_token = auth_service.create_access_token(user_id)
    refresh_token = auth_service.create_refresh_token(user_id)

    resp = JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Login com 2FA realizado com sucesso!",
            "access_token": access_token,
            "token_type": "bearer",
        },
    )
    _set_refresh_cookie(resp, refresh_token)
    set_csrf_cookie(resp, _IS_PROD)
    return resp
