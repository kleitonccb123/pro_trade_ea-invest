"""
?? Stress Test - Crypto Trade Hub Backend
Simula 100 usu?rios fazendo login e consumindo API simultaneamente

Requisitos:
  pip install locust

Uso:
  locust -f backend/tests/stress/stress_test.py --host=http://localhost:8000 --users 100 --spawn-rate 10
  
  ou para modo headless:
  locust -f backend/tests/stress/stress_test.py --host=http://localhost:8000 --users 100 --spawn-rate 10 --headless --run-time 5m
"""

from locust import HttpUser, task, between
import json
import time
import os

# Credenciais de teste
TEST_EMAIL = os.getenv("TEST_EMAIL", "Test")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "123456789")


class CryptoTradeHubUser(HttpUser):
    """
    Simula um usu?rio real do sistema:
    1. Faz login
    2. Consulta status de bots
    3. Verifica analytics
    4. Valida security headers
    """
    
    wait_time = between(1, 3)  # Espera 1-3 segundos entre tarefas
    
    def on_start(self):
        """Executado quando o usu?rio inicia (antes de qualquer task)"""
        self.token = None
        self.user_id = None
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "LocustStressTest/1.0"
        }
        
        # Fazer login
        self._login()
    
    def _login(self):
        """Fazer login e armazenar token JWT"""
        try:
            response = self.client.post(
                "/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
                catch_response=True,
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.user_id = data.get("user_id")
                
                # Validar security headers na resposta de login
                self._validate_security_headers(response)
                
                response.success()
            else:
                response.failure(f"Login failed with status {response.status_code}")
                print(f"? Login error: {response.text}")
        except Exception as e:
            print(f"? Login exception: {e}")
    
    def _validate_security_headers(self, response):
        """Valida presen?a dos 7 security headers"""
        required_headers = {
            "Strict-Transport-Security": "HSTS",
            "X-Content-Type-Options": "MIME sniff protection",
            "X-Frame-Options": "Clickjacking protection",
            "X-XSS-Protection": "XSS legacy protection",
            "Content-Security-Policy": "CSP",
            "Referrer-Policy": "Privacy",
            "Permissions-Policy": "Feature policy",
        }
        
        headers_found = 0
        for header_name, description in required_headers.items():
            if header_name in response.headers:
                headers_found += 1
            else:
                print(f"??  Missing header: {header_name} ({description})")
        
        if headers_found < len(required_headers):
            print(f"??  Only {headers_found}/{len(required_headers)} security headers found!")
    
    def _get_auth_headers(self):
        """Retorna headers com token JWT"""
        if not self.token:
            self._login()
        
        headers = self.headers.copy()
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    @task(3)
    def get_user_profile(self):
        """Tarefa: Consultar perfil do usu?rio (peso 3)"""
        with self.client.get(
            "/me",
            headers=self._get_auth_headers(),
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                # Token expirou, fazer login novamente
                self._login()
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(4)
    def list_bots(self):
        """Tarefa: Listar bots do usu?rio (peso 4)"""
        with self.client.get(
            "/bots",
            headers=self._get_auth_headers(),
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code in [200, 401]:
                if response.status_code == 401:
                    self._login()
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(2)
    def get_analytics(self):
        """Tarefa: Consultar analytics (peso 2)"""
        with self.client.get(
            "/analytics/dashboard",
            headers=self._get_auth_headers(),
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code in [200, 401]:
                if response.status_code == 401:
                    self._login()
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(2)
    def get_trading_history(self):
        """Tarefa: Consultar hist?rico de trading (peso 2)"""
        with self.client.get(
            "/trading/history",
            headers=self._get_auth_headers(),
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code in [200, 401]:
                if response.status_code == 401:
                    self._login()
                response.success()
            else:
                response.failure(f"Status {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Tarefa: Health check (peso 1) - n?o requer auth"""
        with self.client.get(
            "/health",
            headers=self.headers,
            catch_response=True,
            timeout=5
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed with {response.status_code}")
