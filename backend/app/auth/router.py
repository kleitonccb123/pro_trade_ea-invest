from __future__ import annotations

import sys
# Garante que `print()` com emojis não quebre no Windows (cp1252)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import APIRouter, HTTPException, status, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
from typing import Optional
import os
import logging
import re
import requests  # Para trocar code por token no Google OAuth

from app.auth import schemas, service as auth_service
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.core.rate_limiter import check_rate_limit, check_rate_limit_async
from app.middleware.csrf import set_csrf_cookie

# Google OAuth validation
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)

_IS_PROD = os.getenv("APP_MODE", "dev") == "prod"
_REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: JSONResponse, token: str) -> None:
    """Attach the refresh token as a Secure, HttpOnly cookie."""
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_IS_PROD,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/",  # Changed from "/api/auth" to "/" to be available for all requests
    )

# Email validation regex (RFC 5322 simplified)
EMAIL_REGEX = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
EMAIL_PATTERN = re.compile(EMAIL_REGEX)

# 🔐 Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
FRONTEND_REDIRECT_URI = os.getenv("FRONTEND_REDIRECT_URI", "http://localhost:8081/auth-callback")

# ⚠️ VALIDAÇÃO CRÍTICA ao iniciar servidor
if not GOOGLE_CLIENT_ID:
    err = "❌ CRÍTICO: GOOGLE_CLIENT_ID não configurado no .env"
    logger.critical(err)
    print(f"\n{'='*70}\n{err}\n{'='*70}\n")
if not GOOGLE_CLIENT_SECRET:
    err = "❌ CRÍTICO: GOOGLE_CLIENT_SECRET não configurado no .env"
    logger.critical(err)
    print(f"\n{'='*70}\n{err}\n{'='*70}\n")
else:
    logger.info("[STARTUP] Google OAuth configurado corretamente")

def validate_google_token(token: str) -> dict:
    """
    ✅ VALIDAÇÃO BLINDADA DE TOKEN GOOGLE
    
    Etapas:
    1. Verificar GOOGLE_CLIENT_ID (OBRIGATÓRIO)
    2. Validar assinatura com Google
    3. Validar issuer (aceita ambos: com/sem https://)
    4. Extrair dados do usuário
    5. Validar dados obrigatórios
    """
    
    logger.debug("[GOOGLE_TOKEN] Iniciando validação de token")
    
    # [1] Verificar configuração
    if not GOOGLE_CLIENT_ID:
        logger.error("[GOOGLE_TOKEN] GOOGLE_CLIENT_ID não configurado!")
        raise HTTPException(status_code=500, detail="Google OAuth não configurado")
    
    # [2] Validar assinatura
    try:
        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10
        )
        logger.debug("[GOOGLE_TOKEN] Assinatura válida")
    except ValueError as e:
        err = str(e)
        logger.warning("[GOOGLE_TOKEN] Token inválido: %s", err)
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    except Exception as e:
        logger.warning("[GOOGLE_TOKEN] Erro: %s", type(e).__name__)
        raise HTTPException(status_code=401, detail=f"Erro: {type(e).__name__}")
    
    # [3] Validar Issuer
    issuer = id_info.get('iss', 'MISSING')
    valid = issuer in ['accounts.google.com', 'https://accounts.google.com']
    if not valid:
        logger.warning("[GOOGLE_TOKEN] Issuer inválido: %s", issuer)
        raise HTTPException(status_code=401, detail="Issuer inválido")
    
    # [4] Extrair dados
    email = id_info.get('email', '')
    name = id_info.get('name', 'Unknown')
    sub = id_info.get('sub', '')
    # Log masked values to avoid PII in logs
    _email_masked = (email[:3] + "***@" + email.split("@")[-1]) if "@" in email else "***"
    logger.debug("[GOOGLE_TOKEN] Dados extraídos para: %s", _email_masked)
    
    # [5] Validar obrigatórios
    if not email or not sub:
        logger.warning("[GOOGLE_TOKEN] Dados obrigatórios ausentes no token")
        raise HTTPException(status_code=400, detail="Email ou ID faltando")
    
    logger.info("[GOOGLE_TOKEN] Token validado com sucesso")
    return id_info

def validate_email_format(email: str) -> bool:
    """
    Valida se o email tem um formato válido.
    
    Args:
        email: Email a validar
        
    Returns:
        bool: True se válido, False caso contrário
    """
    if not email or len(email) > 254:  # RFC 5321
        return False
    return EMAIL_PATTERN.match(email) is not None

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ============================================================
# PASSWORD STRENGTH VALIDATION
# ============================================================
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_MAX_LENGTH = 128
_PASSWORD_REGEX_UPPER = re.compile(r'[A-Z]')
_PASSWORD_REGEX_LOWER = re.compile(r'[a-z]')
_PASSWORD_REGEX_DIGIT = re.compile(r'[0-9]')
_PASSWORD_REGEX_SPECIAL = re.compile(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]')


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validates password strength. Returns (is_valid, error_message).
    Requirements: 8-128 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char.
    """
    if len(password) < _PASSWORD_MIN_LENGTH:
        return False, f"Senha deve ter no mínimo {_PASSWORD_MIN_LENGTH} caracteres"
    if len(password) > _PASSWORD_MAX_LENGTH:
        return False, f"Senha deve ter no máximo {_PASSWORD_MAX_LENGTH} caracteres"
    if not _PASSWORD_REGEX_UPPER.search(password):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    if not _PASSWORD_REGEX_LOWER.search(password):
        return False, "Senha deve conter pelo menos uma letra minúscula"
    if not _PASSWORD_REGEX_DIGIT.search(password):
        return False, "Senha deve conter pelo menos um número"
    if not _PASSWORD_REGEX_SPECIAL.search(password):
        return False, "Senha deve conter pelo menos um caractere especial (!@#$%...)"
    return True, ""


# ============================================================
# REGISTRO (Email + Senha)
# ============================================================
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: schemas.UserCreate, request: Request):
    """
    Registra um novo usuário com email e senha
    """
    try:
        # ── IP rate limit: 5 registrations per hour per IP (DOC-10) ──────────────
        client_ip = request.client.host if request.client else "unknown"
        allowed, rl_info = await check_rate_limit_async(
            identifier=f"register:{client_ip}",
            max_requests=5,
            window_seconds=3600,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": (
                        f"Muitos cadastros deste IP. "
                        f"Tente novamente em {rl_info['reset_in_seconds']} segundos."
                    ),
                    "retry_after_seconds": rl_info["reset_in_seconds"],
                },
                headers={"Retry-After": str(rl_info["reset_in_seconds"])},
            )

        # ✓ Email validation
        if not validate_email_format(req.email):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Formato de email inválido"}
            )

        # ✓ Password strength validation
        pw_valid, pw_msg = validate_password_strength(req.password)
        if not pw_valid:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": pw_msg}
            )
        
        # Obter IP e User-Agent para logging
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        db = get_db()
        users_col = db.users
        
        # Verificar se usuário já existe
        existing = await users_col.find_one({"email": req.email.lower()})
        if existing:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Usuário com este email já existe"}
            )
        
        # Criar novo usu?rio
        hashed_password = get_password_hash(req.password)
        user_doc = {
            "_id": ObjectId(),
            "email": req.email.lower(),
            "name": req.name or "",
            "hashed_password": hashed_password,
            "auth_provider": "local",
            "google_id": None,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        result = await users_col.insert_one(user_doc)
        
        # 🎮 Create initial gamification profile for new user
        user_id_str = str(result.inserted_id)
        try:
            from app.gamification.service import GameProfileService
            await GameProfileService.get_or_create_profile(user_id_str)
            logger.info(f"✅ GameProfile criado para novo usuário {user_id_str}")
        except Exception as profile_error:
            logger.error(f"⚠️ Erro ao criar GameProfile para {user_id_str}: {str(profile_error)}")

        # 📧 Send email verification link (P1-05)
        try:
            from app.auth.email_service import create_verification_token, send_verification_email
            v_token = await create_verification_token(req.email.lower())
            await send_verification_email(to_email=req.email.lower(), token=v_token, name=req.name or "")
        except Exception as _ev:
            logger.warning(f"Não foi possível enviar email de verificação: {_ev}")
        
        # Gerar tokens
        access_token = auth_service.create_access_token(user_id_str)
        refresh_token = auth_service.create_refresh_token(user_id_str)

        resp = JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Usu?rio criado com sucesso!",
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user_id_str,
                    "email": user_doc["email"],
                    "name": user_doc["name"]
                }
            }
        )
        _set_refresh_cookie(resp, refresh_token)
        set_csrf_cookie(resp, _IS_PROD)
        return resp
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erro ao registrar: {str(e)}"}
        )


# ============================================================
# LOGIN (Email + Senha)
# ============================================================
@router.post("/login")
async def login(req: schemas.LoginRequest, request: Request):
    """
    Faz login com email e senha
    """
    logger.info("[LOGIN] Tentativa de login recebida")
    
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    
    # ✓ Email validation
    if not validate_email_format(req.email):
        logger.debug("[LOGIN] Formato de email inválido")
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Formato de email inválido"}
        )
    
    # Obter IP e User-Agent para logging
    user_agent = request.headers.get("user-agent")
    
    try:
        # ✅ Importar o manager do local_db (sem circular import)
        from app.core.local_db_manager import get_local_db
        
        db = get_local_db()
        
        # Buscar usuário no SQLite local
        logger.debug("[LOGIN] Buscando usuário...")
        user = await db.find_user_by_email(req.email.lower())
        if not user:
            logger.warning("[LOGIN] Usuário não encontrado")
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Email ou senha incorretos"}
            )
        
        logger.debug("[LOGIN] Usuário encontrado, verificando senha")
        
        # Verificar senha
        password_valid = verify_password(req.password, user["hashed_password"])
        
        if not password_valid:
            logger.warning("[LOGIN] Senha incorreta")
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Email ou senha incorretos"}
            )
        
        # Verificar se ativo
        if not user.get("is_active", True):
            return JSONResponse(
                status_code=403,
                content={"success": False, "message": "Usuário desativado"}
            )
        
        # ── P2-01: 2FA check ──────────────────────────────────────────────
        user_id = str(user["_id"])
        try:
            from app.auth.two_factor import two_factor_service as _2fa_svc
            if await _2fa_svc.is_2fa_enabled(user_id):
                # Issue a short-lived "pending" token instead of full access
                pending_token = auth_service.create_access_token(
                    user_id, scope="2fa_pending", expire_minutes=5
                )
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "requires_2fa": True,
                        "pending_token": pending_token,
                        "message": "Código 2FA necessário — use POST /api/auth/2fa/complete",
                    },
                )
        except Exception as _2fa_err:
            logger.warning("[LOGIN] Falha ao verificar 2FA (continuando): %s", _2fa_err)
        
        # Gerar tokens
        access_token = auth_service.create_access_token(user_id)
        refresh_token = auth_service.create_refresh_token(user_id)

        resp = JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Login realizado com sucesso!",
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user_id,
                    "email": user["email"],
                    "name": user.get("name", "")
                }
            }
        )
        _set_refresh_cookie(resp, refresh_token)
        set_csrf_cookie(resp, _IS_PROD)
        return resp
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erro ao fazer login: {str(e)}"}
        )


# ============================================================
# GOOGLE OAUTH - LOGIN REDIRECT
# ============================================================
@router.get("/google/login")
async def google_login_redirect():
    """
    Redireciona o usuário para a página de login do Google.
    Este endpoint inicia o fluxo de autorização OAuth2.
    """
    if not GOOGLE_CLIENT_ID:
        logger.error("❌ GOOGLE_CLIENT_ID não configurado")
        raise HTTPException(
            status_code=500,
            detail="Google OAuth não está configurado no servidor"
        )
    
    # Construir URL de login do Google
    google_login_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"prompt=consent&"
        f"state=security_token_12345"  # CSRF protection (em produção, usar random)
    )
    
    logger.info(f"🔐 Iniciando login Google: {GOOGLE_CLIENT_ID}")
    
    # Redirecionar para Google
    return RedirectResponse(url=google_login_url)


# ============================================================
# GOOGLE OAUTH - CALLBACK (Authorization Code Exchange)
# ============================================================
@router.get("/google/callback")
async def google_callback(code: str, state: str = None, error: str = None, request: Request = None):
    """
    Callback do Google OAuth2 que recebe o 'code'.
    1. Troca o 'code' por um access token do Google
    2. Valida os dados do usuário
    3. Cria/atualiza o usuário no MongoDB
    4. Gera tokens de sessão
    5. Redireciona para o frontend com token
    """
    # ⚠️ RATE LIMITING: DISABLED FOR DEVELOPMENT
    # client_ip = request.client.host if request and request.client else "unknown"
    # allowed, rate_info = check_rate_limit(
    #     identifier=f"google_callback_{client_ip}",
    #     max_requests=3,
    #     window_seconds=60  # 3 tentativas por minuto por IP
    # )
    # 
    # if not allowed:
    #     logger.warning(
    #         f"🚫 Rate limit exceeded for Google OAuth callback from IP {client_ip}. "
    #         f"Reset in {rate_info['reset_in_seconds']}s"
    #     )
    #     return RedirectResponse(
    #         url=f"{FRONTEND_REDIRECT_URI}?error=rate_limited&detail=Too+many+login+attempts.+Try+again+in+{rate_info['reset_in_seconds']}+seconds"
    #     )
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        logger.error("❌ GOOGLE_CLIENT_ID ou GOOGLE_CLIENT_SECRET não configurados")
        raise HTTPException(
            status_code=500,
            detail="Google OAuth não está configurado no servidor"
        )
    
    # Verificar se houve erro do Google
    if error:
        logger.warning(f"❌ Erro do Google OAuth: {error}")
        return RedirectResponse(
            url=f"{FRONTEND_REDIRECT_URI}?error={error}"
        )
    
    if not code:
        logger.warning("❌ Nenhum 'code' recebido do Google")
        return RedirectResponse(
            url=f"{FRONTEND_REDIRECT_URI}?error=no_code"
        )
    
    try:
        # PASSO 1: Trocar 'code' por access_token do Google
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        response = requests.post(token_url, data=payload, timeout=10)
        token_data = response.json()
        
        if "error" in token_data:
            logger.error(f"❌ Erro ao trocar code por token: {token_data['error']}")
            return RedirectResponse(
                url=f"{FRONTEND_REDIRECT_URI}?error=token_exchange_failed"
            )
        
        google_access_token = token_data.get("access_token")
        id_token_jwt = token_data.get("id_token")
        
        if not id_token_jwt:
            logger.error("❌ Nenhum id_token retornado pelo Google")
            return RedirectResponse(
                url=f"{FRONTEND_REDIRECT_URI}?error=no_id_token"
            )
        
        # PASSO 2: Validar JWT do Google
        user_info = validate_google_token(id_token_jwt)
        
        # PASSO 3: Extrair dados do usuário
        email = user_info.get("email", "").lower()
        name = user_info.get("name", "")
        picture = user_info.get("picture", "")
        google_id = user_info.get("sub", "")
        
        if not email or not google_id:
            logger.error("❌ Email ou Google ID não encontrados no token")
            return RedirectResponse(
                url=f"{FRONTEND_REDIRECT_URI}?error=missing_user_data"
            )
        
        # PASSO 4: Buscar/criar usuário
        db = get_db()
        users_col = db.users
        
        user = await users_col.find_one({"google_id": google_id})
        
        if not user:
            user = await users_col.find_one({"email": email})
        
        if user:
            # Usuário já existe - fazer login
            logger.info(f"✓ Login Google: usuário existente {email}")
            
            update_data = {
                "auth_provider": "google",
                "google_id": google_id,
                "last_login": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if picture:
                update_data["avatar"] = picture
            
            await users_col.update_one(
                {"_id": user["_id"]},
                {"$set": update_data}
            )
            
            user = await users_col.find_one({"_id": user["_id"]})
        else:
            # Novo usuário - registrar
            logger.info(f"✓ Novo usuário Google: {email}")
            
            user_doc = {
                "_id": ObjectId(),
                "email": email,
                "name": name,
                "avatar": picture,
                "hashed_password": "",
                "auth_provider": "google",
                "google_id": google_id,
                "is_active": True,
                "plan": "free",  # Plano padrão para novos usuários
                "credits": 5,  # Créditos iniciais
                "activation_credits": 1,  # 1 slot de ativação
                "activation_credits_used": 0,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "last_login": datetime.utcnow(),
            }
            
            result = await users_col.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            user = user_doc
        
        # PASSO 5: Gerar tokens de sessão
        user_id = str(user["_id"])
        access_token = auth_service.create_access_token(user_id)
        refresh_token = auth_service.create_refresh_token(user_id)
        
        logger.info(f"✓ Autenticação Google bem-sucedida: {email} (ID: {user_id})")
        
        # PASSO 6: Redirecionar para frontend com tokens
        redirect_url = (
            f"{FRONTEND_REDIRECT_URI}?"
            f"access_token={access_token}&"
            f"refresh_token={refresh_token}&"
            f"user_id={user_id}&"
            f"email={email}&"
            f"success=true"
        )
        
        return RedirectResponse(url=redirect_url)
    
    except Exception as e:
        logger.error(f"❌ Erro no callback do Google: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{FRONTEND_REDIRECT_URI}?error=callback_error&detail={str(e)}"
        )


# ============================================================
# GOOGLE OAUTH - TOKEN VALIDATION (JWT)
# ============================================================

@router.post("/google")
async def google_auth(req: schemas.GoogleAuthRequest, request: Request = None):
    """
    Autentica ou registra usuário via Google
    Valida o token JWT com Google antes de criar/atualizar usuário
    """
    
    try:
        logger.debug("[GOOGLE_AUTH] Requisição recebida")
        
        # PASSO 1: Validar token com Google (segurança)
        try:
            user_info = validate_google_token(req.id_token)
            logger.debug("[GOOGLE_AUTH] Token validado com sucesso")
        except HTTPException as e:
            logger.warning("[GOOGLE_AUTH] Token inválido: %s", e.detail)
            raise
        except Exception as e:
            logger.error("[GOOGLE_AUTH] Erro inesperado na validação: %s", type(e).__name__)
            raise HTTPException(
                status_code=401,
                detail=f"Erro ao validar token: {str(e)}"
            )
        
        # Extrair dados do token validado (fonte confiável)
        email = user_info.get("email", "").lower()
        name = user_info.get("name", "")
        picture = user_info.get("picture", "")
        google_id = user_info.get("sub", "")  # 'sub' é o Google ID único
        
        if not email or not google_id:
            raise HTTPException(
                status_code=400,
                detail="Token não contém email ou ID do Google"
            )
        
        # ✅ Usar SQLite em vez de MongoDB
        from app.core.local_db_manager import get_local_db
        local_db = get_local_db()
        
        # PASSO 2: Procurar usuário por email no SQLite
        user = await local_db.find_user_by_email(email)
        
        if user:
            # PASSO 3A: Usuário já existe - fazer login
            logger.debug("[GOOGLE_AUTH] Usuário existente encontrado")
        else:
            # PASSO 3B: Novo usuário - registrar no SQLite
            logger.info("[GOOGLE_AUTH] Criando novo usuário Google")
            
            # Criar usuário no SQLite (sem senha)
            from app.core.security import get_password_hash
            hashed_password = get_password_hash("")  # Sem senha pois é Google OAuth
            
            try:
                import uuid as _uuid
                new_user_id = str(_uuid.uuid4())
                now_iso = datetime.utcnow().isoformat()

                # INSERT completo — todos os campos da tabela
                await local_db._connection.execute(
                    """
                    INSERT INTO users
                        (id, email, username, name, hashed_password, full_name,
                         auth_provider, google_id, is_active, is_superuser,
                         activation_credits, activation_credits_used,
                         created_at, updated_at, last_login)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_user_id,        # id  (UUID)
                        email,              # email
                        "",                 # username
                        name,               # name
                        "",                 # hashed_password  (Google = sem senha)
                        name,               # full_name
                        "google",           # auth_provider
                        google_id,          # google_id
                        1,                  # is_active
                        0,                  # is_superuser
                        0,                  # activation_credits
                        0,                  # activation_credits_used
                        now_iso,            # created_at
                        now_iso,            # updated_at
                        now_iso,            # last_login
                    ),
                )
                await local_db._connection.commit()
                logger.debug("[GOOGLE_AUTH] Novo usuário inserido com sucesso")

                # Recarregar usuário
                user = await local_db.find_user_by_email(email)
                if not user:
                    raise Exception("Falha ao recarregar usuário após inserção")

            except Exception as e:
                logger.error("[GOOGLE_AUTH] Erro ao inserir usuário: %s", str(e))
                raise HTTPException(
                    status_code=500,
                    detail=f"Erro ao criar usuário: {str(e)}"
                )
        
        # PASSO 4: Gerar tokens de sessão
        user_id = str(user["_id"])
        access_token = auth_service.create_access_token(user_id)
        refresh_token = auth_service.create_refresh_token(user_id)

        logger.info("[GOOGLE_AUTH] Autenticação bem-sucedida")

        resp = JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Autenticação Google realizada com sucesso!",
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user_id,
                    "email": user["email"],
                    "name": user.get("name", "")
                }
            }
        )
        _set_refresh_cookie(resp, refresh_token)
        set_csrf_cookie(resp, _IS_PROD)
        return resp
    
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        logger.error("Erro na autenticação Google: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erro na autenticação Google: {str(e)}"}
        )


# ============================================================
# REFRESH TOKEN
# ============================================================
@router.post("/refresh")
async def refresh(
    req: schemas.RefreshRequest = None,
    refresh_token_cookie: Optional[str] = None,
    request: Request = None,
):
    """
    Renova o access token usando refresh token (cookie httpOnly preferência)
    Também renova o refresh token cookie para manter sessão viva
    """
    try:
        # Prefer httpOnly cookie; fall back to request body for backwards-compat
        token = None
        if request:
            token = request.cookies.get(_REFRESH_COOKIE_NAME)
        if not token and req:
            token = req.refresh_token
        if not token:
            logger.warning('[REFRESH] Refresh token não encontrado')
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Refresh token não encontrado"}
            )
        
        try:
            payload = auth_service.decode_token(token)
        except Exception as e:
            logger.error(f'[REFRESH] Erro ao decodificar token: {e}')
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Refresh token expirado ou inválido"}
            )
        
        user_id = payload.get("sub")

        if not user_id:
            logger.error('[REFRESH] Token inválido: sub ausente')
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Token inválido"}
            )

        # Gerar novo access token E renovar refresh token
        access_token = auth_service.create_access_token(user_id)
        new_refresh_token = auth_service.create_refresh_token(user_id)

        resp = JSONResponse(
            status_code=200,
            content={
                "success": True,
                "access_token": access_token,
                "token_type": "bearer"
            }
        )
        
        # Renovar o refresh token cookie (para manter a sessão viva)
        _set_refresh_cookie(resp, new_refresh_token)
        logger.info(f'[REFRESH] ✓ Token renovado para usuário {user_id}')
        
        return resp

    except Exception as e:
        logger.error(f'[REFRESH] Erro inesperado: {e}')
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Refresh token expirado ou inválido"}
        )


# ============================================================
# GET CURRENT USER
# ============================================================
@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Retorna dados do usu?rio autenticado
    """
    try:
        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Token n?o fornecido"}
            )
        
        token = authorization.replace("Bearer ", "")
        payload = auth_service.decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Token inv?lido"}
            )
        
        # Use the same SQLite DB that login uses (get_db() may be in-memory mock)
        from app.core.local_db_manager import get_local_db
        local_db = get_local_db()
        user = await local_db.find_user_by_id(user_id)

        if not user:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Usu?rio n?o encontrado"}
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "user": {
                    "id": str(user["_id"]),
                    "email": user["email"],
                    "name": user.get("name", "")
                }
            }
        )
    
    except Exception as _me_err:
        logger.error(f"[/me] erro inesperado: {_me_err}")
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "N?o autorizado"}
        )


# ============================================================
# LOGOUT
# ============================================================
@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout do usu?rio — revoga o access token e limpa o cookie de refresh.
    """
    import time as _time
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
    if token:
        try:
            payload = auth_service.decode_token(token)
            exp = payload.get("exp", 0)
            remaining = max(0, int(exp - _time.time()))
            if remaining > 0:
                await auth_service.add_to_blacklist(token, remaining)
        except Exception:
            pass  # Blacklist on a best-effort basis
    resp = JSONResponse(
        status_code=200,
        content={"success": True, "message": "Logout realizado com sucesso"}
    )
    resp.delete_cookie(key="refresh_token", path="/api/auth")
    return resp


# ============================================================
# EMAIL VERIFICATION (P1-05)
# ============================================================
@router.get("/verify-email")
async def verify_email(token: str):
    """
    Confirms the user's email address via the one-time token sent on registration.
    """
    from app.auth.email_service import consume_verification_token
    email = await consume_verification_token(token)
    if not email:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Token de verificação inválido ou expirado."}
        )
    # Mark user as email_verified in the local DB
    try:
        from app.core.local_db_manager import get_local_db
        local_db = get_local_db()
        user = await local_db.find_user_by_email(email)
        if user and local_db._connection:
            await local_db._connection.execute(
                "UPDATE users SET email_verified = 1 WHERE email = ?", (email,)
            )
            await local_db._connection.commit()
    except Exception as _upd:
        logger.warning(f"[verify-email] Não foi possível marcar email como verificado: {_upd}")

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "Email verificado com sucesso! Você já pode fazer login."}
    )


# ============================================================
# ?? ACTIVATION CREDITS & PLAN INFO
# ============================================================
@router.get("/profile/activation-credits")
async def get_activation_credits(request: Request):
    """
    Retorna informa??es de cr?ditos de ativa??o do usu?rio.
    
    Response:
    ```json
    {
        "plan": "pro",
        "activation_credits": 5,
        "activation_credits_used": 2,
        "activation_credits_remaining": 3,
        "bots_active_slots": 1,
        "bots_count": 8
    }
    ```
    """
    try:
        # Extrair user_id do token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "N?o autorizado"}
            )
        
        token = auth_header.split("Bearer ")[1]
        payload = auth_service.decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Token inv?lido"}
            )
        
        # Buscar usu?rio
        db = get_db()
        users_col = db["users"]
        user = await users_col.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Usu?rio n?o encontrado"}
            )
        
        # Contar bots com slots ativos
        bots_col = db["bots"]
        active_bots_count = await bots_col.count_documents({
            "user_id": ObjectId(user_id),
            "is_active_slot": True
        })
        total_bots_count = await bots_col.count_documents({
            "user_id": ObjectId(user_id)
        })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "plan": user.get("plan", "starter"),
                "activation_credits": user.get("activation_credits", 1),
                "activation_credits_used": user.get("activation_credits_used", 0),
                "activation_credits_remaining": (
                    user.get("activation_credits", 1) - 
                    user.get("activation_credits_used", 0)
                ),
                "bots_active_slots": active_bots_count,
                "bots_count": total_bots_count
            }
        )
    
    except Exception as e:
        logger.error(f"Failed to get activation credits: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "Erro ao buscar cr?ditos"}
        )


# ============================================================
# 🔓 SECRET ADMIN MODE - INFINITE CREDITS
# ============================================================
@router.post("/admin/create-admin-user")
async def create_admin_user():
    """
    🔓 SECRET ENDPOINT: Cria um usuário admin com créditos infinitos
    Para acesso: POST /api/auth/admin/create-admin-user
    """
    try:
        # Get database connection
        from app.core.local_db_manager import get_local_db
        db = get_local_db()
        
        admin_email = "admin@cryptotrade.com"
        admin_password = "AdminPassword123!"
        
        # Check if admin already exists
        existing_admin = await db.find_user_by_email(admin_email)
        if existing_admin:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "✅ ADMIN USER JÁ EXISTE!",
                    "admin_mode": True,
                    "email": admin_email,
                    "credentials": {
                        "email": admin_email,
                        "password": admin_password,
                        "credits": "INFINITOS (999999)",
                        "role": "SUPERUSER/ADMIN"
                    }
                }
            )
        
        # Create admin user with infinite credits
        hashed_password = get_password_hash(admin_password)
        admin_doc = {
            "_id": ObjectId(),
            "email": admin_email,
            "name": "Admin",
            "username": "admin",
            "full_name": "System Administrator",
            "hashed_password": hashed_password,
            "auth_provider": "local",
            "google_id": None,
            "is_active": True,
            "is_superuser": True,  # 👑 Admin flag
            "plan": "enterprise",
            "activation_credits": 999999,  # ♾️ INFINITE CREDITS
            "activation_credits_used": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "login_count": 0,
            "exchange_api_keys": {}
        }
        
        # Insert admin user
        result = await db.connection.users.insert_one(admin_doc)
        
        # Generate tokens for immediate login
        admin_id_str = str(result.inserted_id)
        access_token = auth_service.create_access_token(admin_id_str)
        refresh_token = auth_service.create_refresh_token(admin_id_str)
        
        logger.warning(f"⚠️  ADMIN MODE ACTIVATED: Admin user created with infinite credits")
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "✅ MODO ADMIN ATIVADO COM SUCESSO!",
                "admin_mode": True,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "credentials": {
                    "email": admin_email,
                    "password": admin_password,
                    "credits": "INFINITOS (999999)",
                    "role": "SUPERUSER/ADMIN",
                    "user_id": admin_id_str
                }
            }
        )
    
    except Exception as e:
        logger.error(f"❌ Erro ao criar admin user: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Erro ao ativar modo admin: {str(e)}"}
        )
