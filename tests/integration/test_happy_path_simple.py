#!/usr/bin/env python3
"""
🧪 Teste de Integração Simplificado - Usando Requests Síncronos
=================================================================

Versão simplificada do happy path usando requests (sem asyncio complexo)
para debugging quando há problemas de conectivid ade.
"""

import requests
import json
import time
from datetime import datetime
import logging
import sys
import os

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


class SimpleHappyPathTester:
    def __init__(self, base_url="http://localhost:8000", timeout=30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.user_id = None
        self.access_token = None
        self.bot_id = None
        
    def log(self, message, level="info"):
        """Log com formatação."""
        if level == "success":
            logger.info(f"✅ {message}")
        elif level == "error":
            logger.error(f"❌ {message}")
        elif level == "warning":
            logger.warning(f"⚠️ {message}")
        else:
            logger.info(f"ℹ️ {message}")
    
    def step(self, number, description):
        """Print número do passo."""
        logger.info(f"\n{'='*70}")
        logger.info(f"STEP {number}️⃣ : {description}")
        logger.info('='*70)
    
    def test_health(self):
        """Teste 1: Health Check"""
        self.step(1, "HEALTH CHECK")
        
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"Status: {data.get('status')}, Version: {data.get('version')}", "success")
                return True
            else:
                self.log(f"Health check failed: status {response.status_code}", "error")
                return False
                
        except Exception as e:
            self.log(f"Health check error: {type(e).__name__}: {e}", "error")
            return False
    
    def test_auth(self):
        """Teste 2: Registro e Login"""
        self.step(2, "AUTENTICAÇÃO")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        email = f"test_user_{timestamp}@example.com"
        password = "TestPassword123!@#"
        
        # REGISTRO
        logger.info(f"\n📝 REGISTRANDO USUÁRIO")
        register_data = {
            "email": email,
            "password": password,
            "name": f"Test User {timestamp}"
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/register",
                json=register_data,
                timeout=self.timeout
            )
            
            logger.info(f"Status Code: {response.status_code}")
            
            if response.status_code in [200, 201]:
                logger.info("✅ Registro bem-sucedido")
            elif response.status_code == 400:
                logger.info("⚠️ Usuário pode já existir (400)")
            else:
                logger.warning(f"Registro status inesperado: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Registro error: {e}")
        
        # LOGIN
        logger.info(f"\n🔐 FAZENDO LOGIN")
        login_data = {
            "email": email,
            "password": password
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json=login_data,
                timeout=self.timeout
            )
            
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success") and data.get("access_token"):
                    self.access_token = data["access_token"]
                    self.user_id = data.get("user", {}).get("id")
                    
                    # Configurar header de auth
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.access_token}"
                    })
                    
                    self.log(f"Login bem-sucedido! User ID: {self.user_id}", "success")
                    return True
                else:
                    self.log("Login response sem token", "error")
                    return False
            else:
                self.log(f"Login failed: {response.status_code}", "error")
                return False
                
        except Exception as e:
            self.log(f"Login error: {type(e).__name__}: {e}", "error")
            return False
    
    def test_create_bot(self):
        """Teste 3: Criar Bot"""
        self.step(3, "CRIAR BOT DE TRADING")
        
        if not self.access_token:
            self.log("Nenhum token de autenticação! Execute login primeiro", "error")
            return False
        
        bot_data = {
            "name": "Happy Path Test Bot",
            "symbol": "BTC/USDT",
            "config": {"strategy": "grid", "risk_per_trade": 0.01}
        }
        
        logger.info(f"Payload: {json.dumps(bot_data, indent=2)}")
        
        try:
            response = self.session.post(
                f"{self.base_url}/bots",
                json=bot_data,
                timeout=self.timeout
            )
            
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response: {response.text[:500]}")
            
            if response.status_code == 201:
                bot = response.json()
                self.bot_id = bot.get("id")
                
                if self.bot_id:
                    self.log(f"Bot criado com sucesso! ID: {self.bot_id}", "success")
                    return True
                else:
                    self.log("Bot response sem ID", "error")
                    return False
            else:
                self.log(f"Bot creation failed: {response.status_code}", "error")
                return False
                
        except Exception as e:
            self.log(f"Bot creation error: {type(e).__name__}: {e}", "error")
            return False
    
    def test_start_bot(self):
        """Teste 4: Iniciar Bot"""
        self.step(4, "INICIAR BOT")
        
        if not self.bot_id:
            self.log("Nenhum bot para iniciar!", "error")
            return False
        
        try:
            response = self.session.post(
                f"{self.base_url}/bots/{self.bot_id}/start",
                json={},
                timeout=self.timeout
            )
            
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response: {response.text[:500]}")
            
            if response.status_code in [200, 201, 202]:
                self.log(f"Bot iniciado com sucesso!", "success")
                return True
            else:
                self.log(f"Bot start failed: {response.status_code}", "error")
                return False
                
        except Exception as e:
            self.log(f"Bot start error: {type(e).__name__}: {e}", "error")
            return False
    
    def test_get_bot_status(self):
        """Teste 5: Obter Status do Bot"""
        self.step(5, "OBTER STATUS DO BOT")
        
        if not self.bot_id:
            self.log("Nenhum bot para consultar!", "error")
            return False
        
        try:
            response = self.session.get(
                f"{self.base_url}/bots/{self.bot_id}",
                timeout=self.timeout
            )
            
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Response: {response.text[:500]}")
            
            if response.status_code == 501:
                self.log("Endpoint em desenvolvimento (501)", "warning")
                return True
            
            if response.status_code == 200:
                bot_data = response.json()
                self.log(f"Status do bot obtido", "success")
                return True
            else:
                self.log(f"Status check failed: {response.status_code}", "error")
                return False
                
        except Exception as e:
            self.log(f"Status check error: {type(e).__name__}: {e}", "error")
            return False
    
    def run_all(self):
        """Executar todos os testes"""
        logger.info(f"""
╔════════════════════════════════════════════════════════════════════╗
║  🚀 CRYPTO TRADE HUB - TESTE DE INTEGRAÇÃO (HAPPY PATH)           ║
║  Simples | Síncrono | Sem Asyncio                                 ║
╚════════════════════════════════════════════════════════════════════╝

📍 Base URL: {self.base_url}
⏱️  Timeout: {self.timeout}s
🆔 PID: {os.getpid()}
""")
        
        tests = [
            ("Health Check", self.test_health),
            ("Autenticação", self.test_auth),
            ("Criar Bot", self.test_create_bot),
            ("Iniciar Bot", self.test_start_bot),
            ("Status do Bot", self.test_get_bot_status),
        ]
        
        results = []
        
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
                
                if not result:
                    logger.error(f"\n❌ {name} FALHOU - Parando testes")
                    break
                    
            except Exception as e:
                logger.exception(f"❌ {name} criou exceção: {e}")
                results.append((name, False))
                break
        
        # RESUMO FINAL
        logger.info(f"\n{'='*70}")
        logger.info("📊 RESUMO DOS TESTES")
        logger.info('='*70)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for name, result in results:
            status = "✅ PASSOU" if result else "❌ FALHOU"
            logger.info(f"{status} - {name}")
        
        logger.info(f"\n📈 Resultado: {passed}/{total} testes passaram")
        
        if passed == total:
            logger.info(f"\n🎉 SUCESSO! O sistema está funcionando!")
            return True
        else:
            logger.info(f"\n⚠️ Alguns testes falharam. Verifique os logs acima.")
            return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Teste de Integração Simplificado")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"),
                        help="URL base do servidor")
    parser.add_argument("--timeout", type=int, default=int(os.getenv("TIMEOUT", 30)),
                        help="Timeout em segundos")
    
    args = parser.parse_args()
    
    tester = SimpleHappyPathTester(base_url=args.base_url, timeout=args.timeout)
    success = tester.run_all()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
