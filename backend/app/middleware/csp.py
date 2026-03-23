"""
🔐 Middleware: Content-Security-Policy para Google OAuth

Engenharia de Segurança especializada em Google Sign-In 3.0
Diferencia ambientes de desenvolvimento vs produção com CSP 3 otimizado.

Detalhe Crítico 1: Google One Tap
   - Requer: frame-src https://accounts.google.com
   - Sem isso: popup de Google One Tap não carrega

Detalhe Crítico 2: Imagens de Perfil
   - Requer: img-src https://*.googleusercontent.com
   - Sem isso: fotos de perfil do usuário não aparecem após login
   - Isso é vital para UX após autenticação bem-sucedida

Referência: https://developers.google.com/identity/gsi/web
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import os
import logging

logger = logging.getLogger(__name__)


class GoogleOAuthCSPMiddleware(BaseHTTPMiddleware):
    """
    Middleware CSP 3 otimizado para Google OAuth 3.0 (GSI)
    
    Características:
    ✅ Suporta Google One Tap (popup automático)
    ✅ Suporta Google Sign-In Button (botão personalizado)
    ✅ Carrega imagens de perfil do usuário
    ✅ Diferencia dev vs production automaticamente
    ✅ Inclui segurança contra XSS enquanto permite OAuth
    """

    # ==========================================
    # 🔒 PRODUCTION CSP (Mais Restritiva)
    # ==========================================
    PRODUCTION_CSP = (
        # Padrão seguro: apenas mesma origem
        "default-src 'self'; "
        
        # Scripts: self + Google OAuth necessário
        # CRÍTICO: Adicionar https://accounts.google.com e https://apis.google.com
        "script-src 'self' "
            "https://accounts.google.com "
            "https://apis.google.com "
            "https://*.gstatic.com "
            "https://www.googletagmanager.com; "
        
        # Conexões: self + todos os endpoints Google necessários para OAuth
        # CRÍTICO: Esta é a diretiva que estava bloqueando CORS
        "connect-src 'self' "
            "https://accounts.google.com "
            "https://accounts.google.co.jp "
            "https://accounts.youtube.com "
            "https://*.googleapis.com "
            "https://play.google.com "
            "https://www.google.com; "
        
        # Imagens: self + perfis Google + assets Google
        # CRÍTICO: https://*.googleusercontent.com é ESSENCIAL para fotos de perfil
        "img-src 'self' data: "
            "https://accounts.google.com "
            "https://*.gstatic.com "
            "https://*.googleapis.com "
            "https://*.googleusercontent.com; "
        
        # Estilos: self + Google (widgets de login precisam de CSS)
        "style-src 'self' 'unsafe-inline' "
            "https://accounts.google.com "
            "https://*.gstatic.com "
            "https://fonts.googleapis.com; "
        
        # Fontes: Google Fonts para UI
        "font-src 'self' data: "
            "https://fonts.gstatic.com "
            "https://*.googleapis.com; "
        
        # iframes: CRÍTICO para Google One Tap popup
        "frame-src https://accounts.google.com; "
        
        # Proteção contra clickjacking via embedding
        "frame-ancestors 'none'; "
        
        # Redirecionamentos apenas para HTTPS
        "upgrade-insecure-requests; "
        
        # Bloqueia plugins
        "object-src 'none'; "
        
        # Apenas as ações de formulário que são permitidas
        "base-uri 'self'; "
        "form-action 'self';"
    )

    # ==========================================
    # 🧪 DEVELOPMENT CSP (Mais Permissiva)
    # ==========================================
    DEVELOPMENT_CSP = (
        # Padrão seguro: apenas mesma origem
        "default-src 'self'; "
        
        # Scripts: self + unsafe (para hot-reload Vite) + Google OAuth
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://accounts.google.com "
            "https://apis.google.com "
            "https://*.gstatic.com "
            "https://www.googletagmanager.com; "
        
        # Conexões: self + localhost + Google OAuth
        # CRÍTICO: Inclui conexões para dev server Vite + WebSocket
        "connect-src 'self' "
            "https://accounts.google.com "
            "https://accounts.google.co.jp "
            "https://*.googleapis.com "
            "https://*.google.com "
            "https://play.google.com "
            "http://localhost:8000 "
            "http://localhost:8081 "
            "ws://localhost:8081 "
            "http://0.0.0.0:8000 "
            "http://0.0.0.0:8081 "
            "ws://0.0.0.0:8081; "
        
        # Imagens: permissivo em dev (https) + Google
        "img-src 'self' data: https: "
            "https://*.googleusercontent.com; "
        
        # Estilos: permissivo em dev
        "style-src 'self' 'unsafe-inline' https:; "
        
        # Fontes: permissivo em dev
        "font-src 'self' data: https:; "
        
        # iframes: Google One Tap
        "frame-src https://accounts.google.com; "
        
        # Bloqueia plugins
        "object-src 'none'; "
        
        # Base restrita
        "base-uri 'self';"
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Aplicar CSP dinamicamente baseado no ambiente
        """
        response = await call_next(request)
        
        # Detectar ambiente
        environment = os.getenv("ENVIRONMENT", "development").lower()
        is_production = environment == "production" or environment == "prod"
        
        # Selecionar política CSP apropriada
        csp_policy = self.PRODUCTION_CSP if is_production else self.DEVELOPMENT_CSP
        
        # 🔐 Aplicar Content-Security-Policy
        response.headers["Content-Security-Policy"] = csp_policy
        
        # Log da política aplicada (sem exposição de detalhes em prod)
        mode = "🔒 PRODUCTION" if is_production else "🧪 DEVELOPMENT"
        logger.debug(f"CSP Applied [{mode}] for {request.url.path}")
        
        return response

    @staticmethod
    def get_csp_policy(is_production: bool) -> str:
        """
        Método estático para obter política CSP sem instanciar middleware
        (útil para testes e configuração manual)
        """
        return (
            GoogleOAuthCSPMiddleware.PRODUCTION_CSP 
            if is_production 
            else GoogleOAuthCSPMiddleware.DEVELOPMENT_CSP
        )


# ==========================================
# 📋 Documentação de Diretivas CSP 3
# ==========================================
"""
DIRETIVA              | FUNÇÃO                    | GOOGLE OAUTH PRECISA?
─────────────────────┼──────────────────────────┼─────────────────────
script-src            | Controla scripts          | ✅ SIM (gsi/client)
connect-src           | Fetch/XMLHttpRequest/XHR  | ✅ CRÍTICO (login)
frame-src             | iframes                   | ✅ SIM (One Tap)
img-src               | Imagens                   | ✅ SIM (fotos perfil)
style-src             | CSS/estilos               | ✅ SIM (widgets)
font-src              | Fontes                    | ✅ SIM (Google Fonts)
default-src           | Fallback padrão           | ✅ SIM (base)
frame-ancestors       | Prevent embedding         | ✅ SIM (segurança)
object-src            | Plugins Flash/etc         | ❌ 'none' seguro
base-uri              | Links <base>              | ✅ SIM (restringir)
form-action           | Envio de formulários      | ✅ SIM (restringir)

PROBLEMA RESOLVIDO:
─────────────────
O erro "Requisição cross-origin bloqueada" era causado por:

❌ ANTES: connect-src 'self'
   ↳ Bloqueia requisições para https://accounts.google.com
   ↳ Bloqueia requisições para https://*.googleapis.com
   ↳ LOGIN FALHA SILENCIOSAMENTE

✅ DEPOIS: connect-src 'self' https://accounts.google.com https://*.googleapis.com
   ↳ Permite comunicação com Google OAuth
   ↳ LOGIN FUNCIONA

DETALHE CRÍTICO NÃO ÓBVIO:
───────────────────────────
Se você incluir img-src mas ESQUECER https://*.googleusercontent.com:
   ✅ Login funciona (usuário consegue fazer login)
   ❌ Foto de perfil NÃO aparece (quebra a UI)
   
Sempre incluir: img-src ... https://*.googleusercontent.com ...
"""

# ==========================================
# 🧪 Testes de Validação
# ==========================================
"""
Para validar se a CSP está funcionando:

1. Testar no DevTools (F12):
   fetch('https://accounts.google.com/gsi/client')
     .then(r => console.log('✅ Google Script OK'))
     .catch(e => console.log('❌ Erro:', e.message))

2. Verificar headers:
   curl -I http://localhost:8000/health
   
   Deve conter:
   Content-Security-Policy: default-src 'self'; script-src ...

3. Testar CORS:
   curl -H "Origin: http://localhost:8081" \
        -X OPTIONS http://localhost:8000/auth/google -v
        
   Deve ter Access-Control-Allow-Origin no response

4. Extensão Browser CSP Checker:
   Instalar: "CSP Evaluator" (Google)
   Analisar: detecta vulnerabilities na CSP
"""
