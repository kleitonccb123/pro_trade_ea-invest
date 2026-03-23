"""
🔥 Stress Test Suite - Crypto Trade Hub
=========================================

Testa a escalabilidade do sistema simulando:
- 50-100 usuários simultâneos
- 100 robôs criados e iniciados
- Monitoramento de latência e throughput

Uso:
    python stress_test.py --users 50 --bots 100 --duration 60

Requisitos:
    pip install httpx asyncio rich psutil

Author: Crypto Trade Hub
"""

import asyncio
import argparse
import time
import random
import string
import statistics
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict

import httpx

# Tentar importar rich para output bonito
try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️ 'rich' não instalado. Usando output simples.")

# Tentar importar psutil para monitoramento de recursos
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# ============== CONFIGURATION ==============

@dataclass
class TestConfig:
    """Configuração do teste de stress."""
    base_url: str = "http://localhost:8000"
    num_users: int = 50
    num_bots: int = 100
    duration_seconds: int = 60
    ramp_up_seconds: int = 10
    request_timeout: float = 30.0
    
    # Credenciais de teste
    test_email_prefix: str = "stress_user_"
    test_password: str = "StressTest123!"


@dataclass
class RequestMetrics:
    """Métricas de uma requisição."""
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass 
class TestResults:
    """Resultados consolidados do teste."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time_seconds: float = 0.0
    response_times: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    requests_per_endpoint: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    @property
    def requests_per_second(self) -> float:
        if self.total_time_seconds == 0:
            return 0
        return self.total_requests / self.total_time_seconds
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def error_rate(self) -> float:
        return 100 - self.success_rate
    
    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0
        return statistics.mean(self.response_times)
    
    @property
    def p50_response_time(self) -> float:
        if not self.response_times:
            return 0
        return statistics.median(self.response_times)
    
    @property
    def p95_response_time(self) -> float:
        if len(self.response_times) < 2:
            return self.avg_response_time
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[idx]
    
    @property
    def p99_response_time(self) -> float:
        if len(self.response_times) < 2:
            return self.avg_response_time
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.99)
        return sorted_times[idx]


# ============== STRESS TEST CLIENT ==============

class StressTestClient:
    """Cliente para testes de stress."""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.results = TestResults()
        self.active_tokens: Dict[str, str] = {}  # user_id -> token
        self.created_bots: List[str] = []
        self.running = False
        self._lock = asyncio.Lock()
        
        if RICH_AVAILABLE:
            self.console = Console()
        
    async def _make_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        json: Optional[dict] = None
    ) -> RequestMetrics:
        """Faz uma requisição e coleta métricas."""
        url = f"{self.config.base_url}{endpoint}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        start_time = time.perf_counter()
        error_msg = None
        status_code = 0
        success = False
        
        try:
            response = await client.request(
                method=method,
                url=url,
                json=json,
                headers=headers,
                timeout=self.config.request_timeout
            )
            status_code = response.status_code
            success = 200 <= status_code < 400
            
            if not success:
                error_msg = f"HTTP {status_code}"
                
        except httpx.TimeoutException:
            error_msg = "Timeout"
        except httpx.ConnectError:
            error_msg = "Connection Error"
        except Exception as e:
            error_msg = str(e)[:50]
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        metrics = RequestMetrics(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=elapsed_ms,
            success=success,
            error=error_msg
        )
        
        # Atualizar resultados globais
        async with self._lock:
            self.results.total_requests += 1
            self.results.response_times.append(elapsed_ms)
            self.results.requests_per_endpoint[endpoint] += 1
            
            if success:
                self.results.successful_requests += 1
            else:
                self.results.failed_requests += 1
                if error_msg:
                    self.results.errors[error_msg] += 1
        
        return metrics
    
    async def _register_user(self, client: httpx.AsyncClient, user_id: int) -> Optional[str]:
        """Registra um usuário de teste."""
        email = f"{self.config.test_email_prefix}{user_id}@test.local"
        
        # Tentar fazer login primeiro (usuário pode já existir)
        login_result = await self._make_request(
            client, "POST", "/auth/login",
            json={"email": email, "password": self.config.test_password}
        )
        
        if login_result.success:
            try:
                response = await client.post(
                    f"{self.config.base_url}/auth/login",
                    json={"email": email, "password": self.config.test_password}
                )
                data = response.json()
                return data.get("access_token")
            except:
                pass
        
        # Se login falhou, registrar novo usuário
        register_result = await self._make_request(
            client, "POST", "/auth/register",
            json={
                "email": email,
                "password": self.config.test_password,
                "name": f"Stress User {user_id}"
            }
        )
        
        if register_result.success:
            # Fazer login após registro
            try:
                response = await client.post(
                    f"{self.config.base_url}/auth/login",
                    json={"email": email, "password": self.config.test_password}
                )
                data = response.json()
                return data.get("access_token")
            except:
                pass
        
        return None
    
    async def _create_bot(self, client: httpx.AsyncClient, token: str, bot_num: int) -> Optional[str]:
        """Cria um robô de teste."""
        bot_data = {
            "name": f"StressBot_{bot_num}_{random.randint(1000, 9999)}",
            "exchange": random.choice(["binance", "kucoin"]),
            "symbol": random.choice(["BTC/USDT", "ETH/USDT", "SOL/USDT"]),
            "strategy": random.choice(["grid", "dca"]),
            "initial_capital": random.uniform(100, 1000),
            "config": {
                "grid_levels": 5,
                "grid_spacing": 1.0
            }
        }
        
        result = await self._make_request(
            client, "POST", "/bots/",
            token=token,
            json=bot_data
        )
        
        if result.success:
            try:
                response = await client.post(
                    f"{self.config.base_url}/bots/",
                    json=bot_data,
                    headers={"Authorization": f"Bearer {token}"}
                )
                data = response.json()
                return data.get("id")
            except:
                pass
        
        return None
    
    async def _start_bot(self, client: httpx.AsyncClient, token: str, bot_id: str):
        """Inicia um robô."""
        await self._make_request(
            client, "POST", f"/bots/{bot_id}/start",
            token=token
        )
    
    async def _poll_pnl(self, client: httpx.AsyncClient, token: str):
        """Consulta endpoint de PnL."""
        await self._make_request(
            client, "GET", "/audit/pnl/summary",
            token=token
        )
    
    async def _poll_health(self, client: httpx.AsyncClient):
        """Health check."""
        await self._make_request(client, "GET", "/health")
    
    async def _user_session(self, user_id: int):
        """Simula sessão de um usuário."""
        async with httpx.AsyncClient() as client:
            # 1. Login/Register
            token = await self._register_user(client, user_id)
            
            if not token:
                return
            
            async with self._lock:
                self.active_tokens[str(user_id)] = token
            
            # 2. Criar alguns bots
            bots_per_user = max(1, self.config.num_bots // self.config.num_users)
            
            for i in range(bots_per_user):
                if not self.running:
                    break
                    
                bot_id = await self._create_bot(client, token, user_id * 100 + i)
                
                if bot_id:
                    async with self._lock:
                        self.created_bots.append(bot_id)
                    
                    # Iniciar o bot
                    await self._start_bot(client, token, bot_id)
                
                await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # 3. Polling contínuo enquanto o teste roda
            while self.running:
                await self._poll_pnl(client, token)
                await asyncio.sleep(random.uniform(0.5, 2.0))
    
    async def _monitor_resources(self):
        """Monitora recursos do sistema."""
        if not PSUTIL_AVAILABLE:
            return
        
        cpu_samples = []
        memory_samples = []
        
        while self.running:
            cpu_samples.append(psutil.cpu_percent(interval=None))
            memory_samples.append(psutil.virtual_memory().percent)
            await asyncio.sleep(1)
        
        if cpu_samples:
            print(f"\n📊 Recursos do Sistema:")
            print(f"   CPU Média: {statistics.mean(cpu_samples):.1f}%")
            print(f"   CPU Pico: {max(cpu_samples):.1f}%")
            print(f"   Memória Média: {statistics.mean(memory_samples):.1f}%")
            print(f"   Memória Pico: {max(memory_samples):.1f}%")
    
    async def _continuous_health_check(self):
        """Health checks contínuos."""
        async with httpx.AsyncClient() as client:
            while self.running:
                await self._poll_health(client)
                await asyncio.sleep(5)
    
    def _print_live_stats(self):
        """Imprime estatísticas em tempo real."""
        if RICH_AVAILABLE:
            table = Table(title="📊 Stress Test - Live Stats")
            table.add_column("Métrica", style="cyan")
            table.add_column("Valor", style="green")
            
            table.add_row("Total Requests", str(self.results.total_requests))
            table.add_row("RPS", f"{self.results.requests_per_second:.1f}")
            table.add_row("Success Rate", f"{self.results.success_rate:.1f}%")
            table.add_row("Avg Latency", f"{self.results.avg_response_time:.1f}ms")
            table.add_row("Active Users", str(len(self.active_tokens)))
            table.add_row("Bots Created", str(len(self.created_bots)))
            
            return table
        else:
            return (
                f"Requests: {self.results.total_requests} | "
                f"RPS: {self.results.requests_per_second:.1f} | "
                f"Success: {self.results.success_rate:.1f}% | "
                f"Latency: {self.results.avg_response_time:.1f}ms"
            )
    
    async def run(self):
        """Executa o teste de stress."""
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║  🔥 CRYPTO TRADE HUB - STRESS TEST                          ║
╠══════════════════════════════════════════════════════════════╣
║  Target: {self.config.base_url:<50} ║
║  Users: {self.config.num_users:<52} ║
║  Bots: {self.config.num_bots:<53} ║
║  Duration: {self.config.duration_seconds}s{' ':<48} ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        self.running = True
        start_time = time.perf_counter()
        
        # Iniciar tarefas
        tasks = []
        
        # Usuários com ramp-up gradual
        print("🚀 Iniciando ramp-up de usuários...")
        ramp_delay = self.config.ramp_up_seconds / self.config.num_users
        
        for i in range(self.config.num_users):
            task = asyncio.create_task(self._user_session(i))
            tasks.append(task)
            await asyncio.sleep(ramp_delay)
            
            if (i + 1) % 10 == 0:
                print(f"   ✓ {i + 1}/{self.config.num_users} usuários ativos")
        
        # Monitor de recursos
        if PSUTIL_AVAILABLE:
            tasks.append(asyncio.create_task(self._monitor_resources()))
        
        # Health checks contínuos
        tasks.append(asyncio.create_task(self._continuous_health_check()))
        
        # Rodar pelo tempo definido
        print(f"\n⏱️  Executando teste por {self.config.duration_seconds} segundos...\n")
        
        if RICH_AVAILABLE:
            with Live(self._print_live_stats(), refresh_per_second=2, console=self.console) as live:
                remaining = self.config.duration_seconds
                while remaining > 0 and self.running:
                    await asyncio.sleep(1)
                    remaining -= 1
                    live.update(self._print_live_stats())
        else:
            remaining = self.config.duration_seconds
            while remaining > 0 and self.running:
                await asyncio.sleep(5)
                remaining -= 5
                print(self._print_live_stats())
        
        # Parar
        self.running = False
        self.results.total_time_seconds = time.perf_counter() - start_time
        
        print("\n🛑 Finalizando sessões...")
        
        # Cancelar tarefas pendentes
        for task in tasks:
            if not task.done():
                task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Imprimir relatório
        self._print_report()
    
    def _print_report(self):
        """Imprime relatório final."""
        print("""
╔══════════════════════════════════════════════════════════════╗
║                    📊 RELATÓRIO FINAL                        ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        if RICH_AVAILABLE:
            # Tabela de métricas principais
            table = Table(title="Métricas de Performance")
            table.add_column("Métrica", style="cyan", width=25)
            table.add_column("Valor", style="green", width=20)
            table.add_column("Status", style="bold", width=15)
            
            # RPS
            rps = self.results.requests_per_second
            rps_status = "✅ BOM" if rps > 50 else "⚠️ MÉDIO" if rps > 20 else "❌ BAIXO"
            table.add_row("Requests/Segundo (RPS)", f"{rps:.2f}", rps_status)
            
            # Latência
            avg_lat = self.results.avg_response_time
            lat_status = "✅ BOM" if avg_lat < 200 else "⚠️ MÉDIO" if avg_lat < 500 else "❌ ALTO"
            table.add_row("Latência Média", f"{avg_lat:.2f}ms", lat_status)
            table.add_row("Latência P50", f"{self.results.p50_response_time:.2f}ms", "")
            table.add_row("Latência P95", f"{self.results.p95_response_time:.2f}ms", "")
            table.add_row("Latência P99", f"{self.results.p99_response_time:.2f}ms", "")
            
            # Taxa de erro
            err_rate = self.results.error_rate
            err_status = "✅ BOM" if err_rate < 1 else "⚠️ MÉDIO" if err_rate < 5 else "❌ ALTO"
            table.add_row("Taxa de Erro", f"{err_rate:.2f}%", err_status)
            
            # Totais
            table.add_row("Total Requests", str(self.results.total_requests), "")
            table.add_row("Requests OK", str(self.results.successful_requests), "")
            table.add_row("Requests Falhos", str(self.results.failed_requests), "")
            table.add_row("Tempo Total", f"{self.results.total_time_seconds:.1f}s", "")
            
            self.console.print(table)
            
            # Tabela de erros
            if self.results.errors:
                error_table = Table(title="Erros Encontrados")
                error_table.add_column("Tipo de Erro", style="red")
                error_table.add_column("Ocorrências", style="yellow")
                
                for error, count in sorted(self.results.errors.items(), key=lambda x: -x[1]):
                    error_table.add_row(error, str(count))
                
                self.console.print(error_table)
            
            # Tabela de endpoints
            if self.results.requests_per_endpoint:
                endpoint_table = Table(title="Requests por Endpoint")
                endpoint_table.add_column("Endpoint", style="blue")
                endpoint_table.add_column("Requests", style="white")
                
                for endpoint, count in sorted(self.results.requests_per_endpoint.items(), key=lambda x: -x[1]):
                    endpoint_table.add_row(endpoint, str(count))
                
                self.console.print(endpoint_table)
        
        else:
            # Output simples sem rich
            print(f"""
┌─────────────────────────────────────────────────┐
│ MÉTRICAS DE PERFORMANCE                         │
├─────────────────────────────────────────────────┤
│ Requests/Segundo (RPS): {self.results.requests_per_second:>20.2f} │
│ Latência Média:         {self.results.avg_response_time:>17.2f}ms │
│ Latência P50:           {self.results.p50_response_time:>17.2f}ms │
│ Latência P95:           {self.results.p95_response_time:>17.2f}ms │
│ Latência P99:           {self.results.p99_response_time:>17.2f}ms │
│ Taxa de Sucesso:        {self.results.success_rate:>18.2f}% │
│ Taxa de Erro:           {self.results.error_rate:>18.2f}% │
├─────────────────────────────────────────────────┤
│ Total Requests:         {self.results.total_requests:>20} │
│ Requests OK:            {self.results.successful_requests:>20} │
│ Requests Falhos:        {self.results.failed_requests:>20} │
│ Tempo Total:            {self.results.total_time_seconds:>18.1f}s │
└─────────────────────────────────────────────────┘
            """)
            
            if self.results.errors:
                print("\n⚠️ Erros encontrados:")
                for error, count in self.results.errors.items():
                    print(f"   - {error}: {count}x")
        
        # Avaliação final
        print("\n" + "="*60)
        
        score = 0
        if self.results.requests_per_second > 50:
            score += 1
        if self.results.avg_response_time < 200:
            score += 1
        if self.results.error_rate < 1:
            score += 1
        
        if score == 3:
            print("🏆 RESULTADO: EXCELENTE - Sistema pronto para produção!")
        elif score == 2:
            print("✅ RESULTADO: BOM - Sistema estável, mas pode melhorar")
        elif score == 1:
            print("⚠️ RESULTADO: MÉDIO - Considere otimizações antes de produção")
        else:
            print("❌ RESULTADO: CRÍTICO - Sistema precisa de otimização urgente")
        
        print("="*60)


# ============== MAIN ==============

def main():
    parser = argparse.ArgumentParser(
        description="🔥 Stress Test para Crypto Trade Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python stress_test.py --users 50 --bots 100 --duration 60
  python stress_test.py --url http://api.exemplo.com --users 100
  python stress_test.py --quick  # Teste rápido (10 users, 30s)
        """
    )
    
    parser.add_argument(
        "--url", "-u",
        default="http://localhost:8000",
        help="URL base do backend (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--users", "-n",
        type=int,
        default=50,
        help="Número de usuários simultâneos (default: 50)"
    )
    parser.add_argument(
        "--bots", "-b",
        type=int,
        default=100,
        help="Número de robôs a criar (default: 100)"
    )
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=60,
        help="Duração do teste em segundos (default: 60)"
    )
    parser.add_argument(
        "--ramp-up", "-r",
        type=int,
        default=10,
        help="Tempo de ramp-up em segundos (default: 10)"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Teste rápido (10 users, 20 bots, 30s)"
    )
    
    args = parser.parse_args()
    
    # Configuração
    if args.quick:
        config = TestConfig(
            base_url=args.url,
            num_users=10,
            num_bots=20,
            duration_seconds=30,
            ramp_up_seconds=5
        )
    else:
        config = TestConfig(
            base_url=args.url,
            num_users=args.users,
            num_bots=args.bots,
            duration_seconds=args.duration,
            ramp_up_seconds=args.ramp_up
        )
    
    # Executar
    client = StressTestClient(config)
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n\n⚠️ Teste interrompido pelo usuário")
        client.running = False


if __name__ == "__main__":
    main()
