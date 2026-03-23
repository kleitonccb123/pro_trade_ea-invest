"""
🦗 Locust Stress Test - Crypto Trade Hub
==========================================

Teste de stress profissional com dashboard web.

Instalação:
    pip install locust

Uso:
    # Com interface web (dashboard)
    locust -f locustfile.py --host=http://localhost:8000
    
    # Headless (sem interface)
    locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 60s
    
    # Abrir http://localhost:8089 para dashboard

Parâmetros:
    -u, --users     Número de usuários
    -r, --spawn-rate Taxa de criação de usuários/segundo
    -t, --run-time   Tempo de execução (ex: 60s, 5m)

Author: Crypto Trade Hub
"""

import random
import time
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner

# Contadores globais
class Stats:
    bots_created = 0
    bots_started = 0
    logins_success = 0
    logins_failed = 0


# ============== USER BEHAVIORS ==============

class CryptoTraderUser(HttpUser):
    """
    Simula um usuário típico da plataforma.
    
    Comportamento:
    1. Faz login
    2. Cria robôs
    3. Inicia robôs
    4. Consulta PnL periodicamente
    5. Verifica status dos robôs
    """
    
    # Tempo de espera entre tasks (1-3 segundos)
    wait_time = between(1, 3)
    
    # Token de autenticação
    token = None
    user_id = None
    my_bots = []
    
    def on_start(self):
        """Executado quando o usuário inicia."""
        self._login_or_register()
    
    def _login_or_register(self):
        """Faz login ou registra novo usuário."""
        # Gerar email único
        self.user_id = f"locust_{random.randint(100000, 999999)}"
        email = f"{self.user_id}@stress.test"
        password = "LocustTest123!"
        
        # Tentar login primeiro
        with self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
            catch_response=True,
            name="/auth/login"
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.token = data.get("access_token")
                    Stats.logins_success += 1
                    response.success()
                    return
                except:
                    pass
        
        # Se login falhou, registrar
        with self.client.post(
            "/auth/register",
            json={
                "email": email,
                "password": password,
                "name": f"Locust User {self.user_id}"
            },
            catch_response=True,
            name="/auth/register"
        ) as response:
            if response.status_code in [200, 201]:
                # Fazer login após registro
                login_resp = self.client.post(
                    "/auth/login",
                    json={"email": email, "password": password}
                )
                if login_resp.status_code == 200:
                    try:
                        self.token = login_resp.json().get("access_token")
                        Stats.logins_success += 1
                        response.success()
                        return
                    except:
                        pass
            
            Stats.logins_failed += 1
            response.failure("Falha no registro/login")
    
    def _get_headers(self):
        """Retorna headers com autenticação."""
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}
    
    # ============== TASKS ==============
    
    @task(10)  # Peso: mais frequente
    def check_pnl_summary(self):
        """Consulta resumo de PnL - endpoint crítico para monitorar."""
        with self.client.get(
            "/audit/pnl/summary",
            headers=self._get_headers(),
            catch_response=True,
            name="/audit/pnl/summary"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                response.failure("Não autorizado")
            else:
                response.failure(f"Erro {response.status_code}")
    
    @task(5)
    def list_bots(self):
        """Lista robôs do usuário."""
        with self.client.get(
            "/bots/",
            headers=self._get_headers(),
            catch_response=True,
            name="/bots/ [LIST]"
        ) as response:
            if response.status_code == 200:
                try:
                    bots = response.json()
                    # Atualizar lista local de bots
                    if isinstance(bots, list):
                        self.my_bots = [b.get("id") for b in bots if b.get("id")]
                except:
                    pass
                response.success()
            else:
                response.failure(f"Erro {response.status_code}")
    
    @task(3)
    def create_bot(self):
        """Cria um novo robô."""
        bot_data = {
            "name": f"LocustBot_{self.user_id}_{random.randint(1000, 9999)}",
            "exchange": random.choice(["binance", "kucoin", "bybit"]),
            "symbol": random.choice(["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]),
            "strategy": random.choice(["grid", "dca", "scalping"]),
            "initial_capital": random.uniform(100, 5000),
            "config": {
                "grid_levels": random.randint(3, 10),
                "grid_spacing": random.uniform(0.5, 2.0)
            }
        }
        
        with self.client.post(
            "/bots/",
            json=bot_data,
            headers=self._get_headers(),
            catch_response=True,
            name="/bots/ [CREATE]"
        ) as response:
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    bot_id = data.get("id")
                    if bot_id:
                        self.my_bots.append(bot_id)
                        Stats.bots_created += 1
                except:
                    pass
                response.success()
            elif response.status_code == 401:
                response.failure("Não autorizado")
            else:
                response.failure(f"Erro {response.status_code}")
    
    @task(2)
    def start_bot(self):
        """Inicia um robô aleatório."""
        if not self.my_bots:
            return
        
        bot_id = random.choice(self.my_bots)
        
        with self.client.post(
            f"/bots/{bot_id}/start",
            headers=self._get_headers(),
            catch_response=True,
            name="/bots/{id}/start"
        ) as response:
            if response.status_code == 200:
                Stats.bots_started += 1
                response.success()
            elif response.status_code == 404:
                # Bot não existe mais, remover da lista
                if bot_id in self.my_bots:
                    self.my_bots.remove(bot_id)
                response.success()  # Não é erro do sistema
            else:
                response.failure(f"Erro {response.status_code}")
    
    @task(2)
    def stop_bot(self):
        """Para um robô aleatório."""
        if not self.my_bots:
            return
        
        bot_id = random.choice(self.my_bots)
        
        with self.client.post(
            f"/bots/{bot_id}/stop",
            headers=self._get_headers(),
            catch_response=True,
            name="/bots/{id}/stop"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                if bot_id in self.my_bots:
                    self.my_bots.remove(bot_id)
                response.success()
            else:
                response.failure(f"Erro {response.status_code}")
    
    @task(1)
    def get_bot_status(self):
        """Verifica status de um robô específico."""
        if not self.my_bots:
            return
        
        bot_id = random.choice(self.my_bots)
        
        with self.client.get(
            f"/bots/{bot_id}",
            headers=self._get_headers(),
            catch_response=True,
            name="/bots/{id} [GET]"
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Erro {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Verifica saúde do sistema."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Sistema unhealthy: {response.status_code}")


class AggressiveTrader(HttpUser):
    """
    Usuário agressivo - faz muitas operações rápidas.
    Simula traders de alta frequência.
    """
    
    wait_time = between(0.1, 0.5)  # Muito mais rápido
    token = None
    user_id = None
    my_bots = []
    
    def on_start(self):
        """Login rápido."""
        self.user_id = f"aggressive_{random.randint(100000, 999999)}"
        email = f"{self.user_id}@aggressive.test"
        password = "Aggressive123!"
        
        # Registrar e logar
        self.client.post(
            "/auth/register",
            json={"email": email, "password": password, "name": f"Aggressive {self.user_id}"}
        )
        
        response = self.client.post(
            "/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            try:
                self.token = response.json().get("access_token")
            except:
                pass
    
    def _get_headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}
    
    @task(20)
    def rapid_pnl_check(self):
        """Consulta PnL muito frequentemente."""
        self.client.get(
            "/audit/pnl/summary",
            headers=self._get_headers(),
            name="/audit/pnl/summary [RAPID]"
        )
    
    @task(10)
    def rapid_bot_list(self):
        """Lista bots frequentemente."""
        response = self.client.get(
            "/bots/",
            headers=self._get_headers(),
            name="/bots/ [RAPID]"
        )
        if response.status_code == 200:
            try:
                bots = response.json()
                if isinstance(bots, list):
                    self.my_bots = [b.get("id") for b in bots if b.get("id")]
            except:
                pass
    
    @task(5)
    def rapid_create_start(self):
        """Cria e inicia bot rapidamente."""
        # Criar
        bot_data = {
            "name": f"RapidBot_{random.randint(10000, 99999)}",
            "exchange": "binance",
            "symbol": "BTC/USDT",
            "strategy": "grid",
            "initial_capital": 500
        }
        
        response = self.client.post(
            "/bots/",
            json=bot_data,
            headers=self._get_headers(),
            name="/bots/ [RAPID CREATE]"
        )
        
        if response.status_code in [200, 201]:
            try:
                bot_id = response.json().get("id")
                if bot_id:
                    # Iniciar imediatamente
                    self.client.post(
                        f"/bots/{bot_id}/start",
                        headers=self._get_headers(),
                        name="/bots/{id}/start [RAPID]"
                    )
            except:
                pass


# ============== EVENT HOOKS ==============

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Executado quando o teste inicia."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║  🦗 LOCUST STRESS TEST - CRYPTO TRADE HUB                    ║
╠══════════════════════════════════════════════════════════════╣
║  Acesse o dashboard em: http://localhost:8089                ║
║  Para parar: Ctrl+C                                          ║
╚══════════════════════════════════════════════════════════════╝
    """)


@events.test_stop.add_listener  
def on_test_stop(environment, **kwargs):
    """Executado quando o teste para."""
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  📊 RESUMO DO TESTE                                          ║
╠══════════════════════════════════════════════════════════════╣
║  Bots Criados:     {Stats.bots_created:<40} ║
║  Bots Iniciados:   {Stats.bots_started:<40} ║
║  Logins OK:        {Stats.logins_success:<40} ║
║  Logins Falhos:    {Stats.logins_failed:<40} ║
╚══════════════════════════════════════════════════════════════╝
    """)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Log de cada request (opcional - para debugging)."""
    # Descomente para debug:
    # if exception:
    #     print(f"❌ {request_type} {name}: {exception}")
    # elif response.status_code >= 400:
    #     print(f"⚠️ {request_type} {name}: {response.status_code}")
    pass


# ============== CUSTOM SHAPES (Opcional) ==============

class StagesShape:
    """
    Define estágios de carga personalizados.
    Use com: locust -f locustfile.py --class-picker
    """
    
    stages = [
        # (duração em segundos, número de usuários, spawn rate)
        {"duration": 30, "users": 10, "spawn_rate": 2},    # Warmup
        {"duration": 60, "users": 50, "spawn_rate": 5},    # Carga média
        {"duration": 60, "users": 100, "spawn_rate": 10},  # Carga alta
        {"duration": 30, "users": 50, "spawn_rate": 5},    # Cooldown
        {"duration": 30, "users": 10, "spawn_rate": 2},    # Final
    ]
    
    def tick(self):
        run_time = self.get_run_time()
        
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
            run_time -= stage["duration"]
        
        return None  # Fim do teste


# ============== CONFIGURAÇÃO PADRÃO ==============

# Se você quer rodar com config específica via código:
# locust -f locustfile.py --config locust.conf

"""
Exemplo de locust.conf:

[locust]
locustfile = locustfile.py
host = http://localhost:8000
users = 50
spawn-rate = 5
run-time = 2m
headless = false
"""
