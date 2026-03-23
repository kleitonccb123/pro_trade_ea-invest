"""
📊 MongoDB Performance Monitor
==============================

Monitora o MongoDB durante testes de stress para identificar gargalos.

Uso:
    python mongo_monitor.py --uri mongodb://localhost:27017 --db crypto_trade_hub --interval 2

Métricas monitoradas:
- Operações por segundo (inserts, queries, updates, deletes)
- Conexões ativas
- Uso de memória
- Latência de operações
- Lock percentage

Author: Crypto Trade Hub
"""

import asyncio
import argparse
import time
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    print("⚠️ Motor não instalado. Execute: pip install motor")

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.layout import Layout
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class MongoMetrics:
    """Métricas do MongoDB."""
    timestamp: datetime
    
    # Operações
    inserts_per_sec: float = 0
    queries_per_sec: float = 0
    updates_per_sec: float = 0
    deletes_per_sec: float = 0
    commands_per_sec: float = 0
    
    # Conexões
    current_connections: int = 0
    available_connections: int = 0
    
    # Memória (MB)
    resident_memory_mb: float = 0
    virtual_memory_mb: float = 0
    
    # Performance
    page_faults: int = 0
    lock_percent: float = 0
    
    # Network
    bytes_in_per_sec: float = 0
    bytes_out_per_sec: float = 0
    
    @property
    def total_ops_per_sec(self) -> float:
        return (
            self.inserts_per_sec + 
            self.queries_per_sec + 
            self.updates_per_sec + 
            self.deletes_per_sec
        )


class MongoMonitor:
    """Monitor de performance do MongoDB."""
    
    def __init__(self, uri: str, database: str, interval: float = 2.0):
        self.uri = uri
        self.database = database
        self.interval = interval
        self.running = False
        
        self.client: Optional[AsyncIOMotorClient] = None
        self.previous_stats: Optional[Dict] = None
        self.previous_time: Optional[float] = None
        self.metrics_history: list[MongoMetrics] = []
        
        if RICH_AVAILABLE:
            self.console = Console()
    
    async def connect(self):
        """Conecta ao MongoDB."""
        if not MOTOR_AVAILABLE:
            raise RuntimeError("Motor não disponível")
        
        self.client = AsyncIOMotorClient(self.uri)
        
        # Testar conexão
        try:
            await self.client.admin.command('ping')
            print(f"✅ Conectado ao MongoDB: {self.uri}")
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            raise
    
    async def get_server_status(self) -> Dict:
        """Obtém status do servidor."""
        return await self.client.admin.command('serverStatus')
    
    async def get_db_stats(self) -> Dict:
        """Obtém estatísticas do database."""
        db = self.client[self.database]
        return await db.command('dbStats')
    
    def calculate_rates(self, current: Dict, previous: Dict, elapsed: float) -> Dict:
        """Calcula taxas por segundo."""
        rates = {}
        
        # Operações
        opcounters = current.get('opcounters', {})
        prev_opcounters = previous.get('opcounters', {})
        
        for op in ['insert', 'query', 'update', 'delete', 'command']:
            current_val = opcounters.get(op, 0)
            prev_val = prev_opcounters.get(op, 0)
            rates[f'{op}_per_sec'] = (current_val - prev_val) / elapsed
        
        # Network
        network = current.get('network', {})
        prev_network = previous.get('network', {})
        
        rates['bytes_in_per_sec'] = (
            network.get('bytesIn', 0) - prev_network.get('bytesIn', 0)
        ) / elapsed
        
        rates['bytes_out_per_sec'] = (
            network.get('bytesOut', 0) - prev_network.get('bytesOut', 0)
        ) / elapsed
        
        return rates
    
    async def collect_metrics(self) -> MongoMetrics:
        """Coleta métricas atuais."""
        status = await self.get_server_status()
        current_time = time.time()
        
        # Calcular rates se temos dados anteriores
        rates = {}
        if self.previous_stats and self.previous_time:
            elapsed = current_time - self.previous_time
            rates = self.calculate_rates(status, self.previous_stats, elapsed)
        
        # Salvar para próxima iteração
        self.previous_stats = status
        self.previous_time = current_time
        
        # Extrair métricas
        connections = status.get('connections', {})
        mem = status.get('mem', {})
        extra_info = status.get('extra_info', {})
        global_lock = status.get('globalLock', {})
        
        # Calcular lock percentage
        lock_current = global_lock.get('currentQueue', {})
        total_queued = lock_current.get('total', 0)
        active_clients = global_lock.get('activeClients', {}).get('total', 1)
        lock_percent = (total_queued / max(active_clients, 1)) * 100
        
        metrics = MongoMetrics(
            timestamp=datetime.now(),
            
            # Operações
            inserts_per_sec=rates.get('insert_per_sec', 0),
            queries_per_sec=rates.get('query_per_sec', 0),
            updates_per_sec=rates.get('update_per_sec', 0),
            deletes_per_sec=rates.get('delete_per_sec', 0),
            commands_per_sec=rates.get('command_per_sec', 0),
            
            # Conexões
            current_connections=connections.get('current', 0),
            available_connections=connections.get('available', 0),
            
            # Memória
            resident_memory_mb=mem.get('resident', 0),
            virtual_memory_mb=mem.get('virtual', 0),
            
            # Performance
            page_faults=extra_info.get('page_faults', 0),
            lock_percent=lock_percent,
            
            # Network
            bytes_in_per_sec=rates.get('bytes_in_per_sec', 0),
            bytes_out_per_sec=rates.get('bytes_out_per_sec', 0)
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def render_dashboard(self, metrics: MongoMetrics) -> Table:
        """Renderiza dashboard com rich."""
        table = Table(title="📊 MongoDB Performance Monitor", expand=True)
        
        table.add_column("Métrica", style="cyan", width=25)
        table.add_column("Valor", style="green", width=15)
        table.add_column("Status", style="bold", width=10)
        
        # Operações
        ops_status = "✅" if metrics.total_ops_per_sec < 1000 else "⚠️" if metrics.total_ops_per_sec < 5000 else "❌"
        table.add_row("Total Ops/sec", f"{metrics.total_ops_per_sec:.1f}", ops_status)
        table.add_row("  ├─ Inserts/sec", f"{metrics.inserts_per_sec:.1f}", "")
        table.add_row("  ├─ Queries/sec", f"{metrics.queries_per_sec:.1f}", "")
        table.add_row("  ├─ Updates/sec", f"{metrics.updates_per_sec:.1f}", "")
        table.add_row("  └─ Deletes/sec", f"{metrics.deletes_per_sec:.1f}", "")
        
        table.add_row("", "", "")  # Separador
        
        # Conexões
        conn_status = "✅" if metrics.current_connections < 100 else "⚠️" if metrics.current_connections < 500 else "❌"
        table.add_row("Conexões Ativas", str(metrics.current_connections), conn_status)
        table.add_row("Conexões Disponíveis", str(metrics.available_connections), "")
        
        table.add_row("", "", "")  # Separador
        
        # Memória
        mem_status = "✅" if metrics.resident_memory_mb < 1024 else "⚠️" if metrics.resident_memory_mb < 4096 else "❌"
        table.add_row("Memória Residente", f"{metrics.resident_memory_mb:.0f} MB", mem_status)
        table.add_row("Memória Virtual", f"{metrics.virtual_memory_mb:.0f} MB", "")
        
        table.add_row("", "", "")  # Separador
        
        # Performance
        lock_status = "✅" if metrics.lock_percent < 5 else "⚠️" if metrics.lock_percent < 20 else "❌"
        table.add_row("Lock %", f"{metrics.lock_percent:.2f}%", lock_status)
        table.add_row("Page Faults", str(metrics.page_faults), "")
        
        table.add_row("", "", "")  # Separador
        
        # Network
        table.add_row("Network In", f"{metrics.bytes_in_per_sec / 1024:.1f} KB/s", "")
        table.add_row("Network Out", f"{metrics.bytes_out_per_sec / 1024:.1f} KB/s", "")
        
        table.add_row("", "", "")
        table.add_row("Última Atualização", metrics.timestamp.strftime("%H:%M:%S"), "")
        
        return table
    
    def print_simple(self, metrics: MongoMetrics):
        """Output simples sem rich."""
        print(f"""
[{metrics.timestamp.strftime('%H:%M:%S')}] MongoDB Metrics:
  Ops/sec: {metrics.total_ops_per_sec:.1f} (I:{metrics.inserts_per_sec:.0f} Q:{metrics.queries_per_sec:.0f} U:{metrics.updates_per_sec:.0f} D:{metrics.deletes_per_sec:.0f})
  Conexões: {metrics.current_connections}/{metrics.available_connections}
  Memória: {metrics.resident_memory_mb:.0f}MB
  Lock: {metrics.lock_percent:.2f}%
        """)
    
    def print_summary(self):
        """Imprime resumo final."""
        if not self.metrics_history:
            return
        
        # Calcular médias (ignorar primeira amostra que pode ter rates zerados)
        valid_metrics = self.metrics_history[1:] if len(self.metrics_history) > 1 else self.metrics_history
        
        if not valid_metrics:
            return
        
        avg_ops = sum(m.total_ops_per_sec for m in valid_metrics) / len(valid_metrics)
        max_ops = max(m.total_ops_per_sec for m in valid_metrics)
        avg_conn = sum(m.current_connections for m in valid_metrics) / len(valid_metrics)
        max_conn = max(m.current_connections for m in valid_metrics)
        avg_mem = sum(m.resident_memory_mb for m in valid_metrics) / len(valid_metrics)
        max_mem = max(m.resident_memory_mb for m in valid_metrics)
        avg_lock = sum(m.lock_percent for m in valid_metrics) / len(valid_metrics)
        max_lock = max(m.lock_percent for m in valid_metrics)
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║              📊 RESUMO DO MONITORAMENTO                      ║
╠══════════════════════════════════════════════════════════════╣
║  Período: {len(self.metrics_history)} amostras coletadas                        
║                                                              ║
║  OPERAÇÕES:                                                  ║
║    Média: {avg_ops:>10.1f} ops/sec                              
║    Pico:  {max_ops:>10.1f} ops/sec                              
║                                                              ║
║  CONEXÕES:                                                   ║
║    Média: {avg_conn:>10.0f}                                     
║    Pico:  {max_conn:>10.0f}                                     
║                                                              ║
║  MEMÓRIA:                                                    ║
║    Média: {avg_mem:>10.0f} MB                                   
║    Pico:  {max_mem:>10.0f} MB                                   
║                                                              ║
║  LOCK:                                                       ║
║    Média: {avg_lock:>10.2f}%                                    
║    Pico:  {max_lock:>10.2f}%                                    
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # Avaliação
        issues = []
        if max_ops > 5000:
            issues.append("⚠️ Pico de operações alto (>5000/sec)")
        if max_conn > 500:
            issues.append("⚠️ Muitas conexões simultâneas (>500)")
        if max_mem > 4096:
            issues.append("⚠️ Alto uso de memória (>4GB)")
        if max_lock > 20:
            issues.append("⚠️ Lock percentage alto (>20%)")
        
        if issues:
            print("\n⚠️ ALERTAS:")
            for issue in issues:
                print(f"   {issue}")
        else:
            print("\n✅ MongoDB performou bem durante o teste!")
    
    async def run(self, duration: Optional[int] = None):
        """Executa o monitor."""
        await self.connect()
        
        self.running = True
        start_time = time.time()
        
        print(f"\n🔍 Monitorando MongoDB a cada {self.interval}s...")
        if duration:
            print(f"⏱️  Duração: {duration}s")
        print("   Pressione Ctrl+C para parar\n")
        
        # Primeira coleta para inicializar
        await self.collect_metrics()
        await asyncio.sleep(self.interval)
        
        try:
            if RICH_AVAILABLE:
                with Live(console=self.console, refresh_per_second=1) as live:
                    while self.running:
                        if duration and (time.time() - start_time) >= duration:
                            break
                        
                        metrics = await self.collect_metrics()
                        live.update(self.render_dashboard(metrics))
                        
                        await asyncio.sleep(self.interval)
            else:
                while self.running:
                    if duration and (time.time() - start_time) >= duration:
                        break
                    
                    metrics = await self.collect_metrics()
                    self.print_simple(metrics)
                    
                    await asyncio.sleep(self.interval)
        
        except KeyboardInterrupt:
            print("\n⚠️ Monitor interrompido")
        
        finally:
            self.running = False
            self.print_summary()
            
            if self.client:
                self.client.close()


async def main():
    parser = argparse.ArgumentParser(
        description="📊 Monitor de Performance do MongoDB",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--uri", "-u",
        default="mongodb://localhost:27017",
        help="URI de conexão do MongoDB"
    )
    parser.add_argument(
        "--db", "-d",
        default="crypto_trade_hub",
        help="Nome do database a monitorar"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=2.0,
        help="Intervalo entre coletas em segundos"
    )
    parser.add_argument(
        "--duration", "-t",
        type=int,
        default=None,
        help="Duração do monitoramento em segundos (None = infinito)"
    )
    
    args = parser.parse_args()
    
    if not MOTOR_AVAILABLE:
        print("❌ Motor não disponível. Execute: pip install motor")
        return
    
    monitor = MongoMonitor(
        uri=args.uri,
        database=args.db,
        interval=args.interval
    )
    
    await monitor.run(duration=args.duration)


if __name__ == "__main__":
    asyncio.run(main())
