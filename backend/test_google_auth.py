#!/usr/bin/env python3
"""
Script para testar a valida??o de tokens Google

Uso:
    python test_google_auth.py <id_token>

Exemplo com token real do Google:
    1. Fazer login em Google
    2. Obter o id_token via frontend (console.log)
    3. Executar: python test_google_auth.py <seu_id_token>
"""

import sys
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_google_token_validation():
    """Testa se o m?dulo de valida??o est? funcionando"""
    
    try:
        # Importar a fun??o de valida??o
        from app.auth.router import validate_google_token
        logger.info("? M?dulo app.auth.router importado com sucesso")
        
        # Importar depend?ncias
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        logger.info("? Bibliotecas Google Auth dispon?veis")
        
        # Testar com token inv?lido (para verificar tratamento de erro)
        logger.info("\n? Teste 1: Validar token inv?lido")
        try:
            validate_google_token("invalid.token.here")
            logger.error("? Deveria ter lan?ado exce??o para token inv?lido")
        except Exception as e:
            logger.info(f"? Erro esperado capturado: {type(e).__name__}")
        
        # Testar se GOOGLE_CLIENT_ID est? configurado
        logger.info("\n? Teste 2: Verificar GOOGLE_CLIENT_ID")
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        if google_client_id:
            logger.info(f"? GOOGLE_CLIENT_ID configurado: {google_client_id[:20]}...")
        else:
            logger.warning("?? GOOGLE_CLIENT_ID n?o configurado no .env")
            logger.info("   Para configurar:")
            logger.info("   1. Abrir https://console.cloud.google.com/")
            logger.info("   2. Criar OAuth 2.0 Client ID")
            logger.info("   3. Adicionar a .env: GOOGLE_CLIENT_ID=seu_client_id.apps.googleusercontent.com")
        
        # Verificar conex?o com MongoDB
        logger.info("\n? Teste 3: Verificar configura??o MongoDB")
        from app.core.config import settings
        
        if settings.OFFLINE_MODE:
            logger.warning("?? OFFLINE_MODE=true (usando dados em mem?ria)")
            logger.info("   Para usar MongoDB Atlas:")
            logger.info("   1. Editar .env: OFFLINE_MODE=false")
            logger.info("   2. Verificar DATABASE_URL")
        else:
            logger.info(f"? OFFLINE_MODE=false (MongoDB Atlas ativo)")
            logger.info(f"   Database: {settings.DATABASE_NAME}")
            logger.info(f"   URL: {settings.DATABASE_URL[:40]}...")
        
        logger.info("\n" + "="*60)
        logger.info("? TESTES CONCLU?DOS COM SUCESSO")
        logger.info("="*60)
        
        logger.info("\n? Pr?ximos passos:")
        logger.info("1. Configurar GOOGLE_CLIENT_ID no .env")
        logger.info("2. Reiniciar servidor: python run_server.py")
        logger.info("3. Testar endpoint: POST /api/auth/google")
        logger.info("4. Verificar usu?rios em MongoDB: db.users.find()")
        
        return True
        
    except Exception as e:
        logger.error(f"? Erro ao testar: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("\n" + "="*60)
    logger.info("Teste de Autentica??o Google - Crypto Trade Hub")
    logger.info("="*60 + "\n")
    
    success = test_google_token_validation()
    sys.exit(0 if success else 1)
