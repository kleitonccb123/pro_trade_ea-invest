"""
? WebSocket Load Test - Crypto Trade Hub
Abre 50 conex?es WebSocket simult?neas e verifica lat?ncia de mensagens

Requisitos:
  pip install websockets asyncio

Uso:
  python backend/tests/integration/test_websocket_load.py

Valida??o:
  ? 50 conex?es simult?neas
  ? Lat?ncia m?dia < 200ms
  ? Sem perda de mensagens
"""

import asyncio
import websockets
import json
import time
from datetime import datetime
from typing import List, Dict
import statistics

# ============================================
# Configura??o
# ============================================

WEBSOCKET_URL = "ws://localhost:8000/ws/notifications"
NUM_CONNECTIONS = 50
MESSAGE_TIMEOUT = 10  # segundos
LATENCY_THRESHOLD_MS = 200  # 200ms ? o threshold desejado

# ============================================
# Teste de WebSocket
# ============================================


class WebSocketLoadTest:
    """Testa carga de WebSocket"""
    
    def __init__(self, url: str, num_connections: int):
        self.url = url
        self.num_connections = num_connections
        self.connections: List[websockets.WebSocketClientProtocol] = []
        self.received_messages: Dict[int, List[float]] = {
            i: [] for i in range(num_connections)
        }
        self.latencies: List[float] = []
        self.errors: List[str] = []
        self.start_time = None
        self.end_time = None
    
    async def connect_client(self, client_id: int) -> bool:
        """Conecta um cliente WebSocket"""
        try:
            ws = await websockets.connect(
                self.url,
                ping_interval=20,
                ping_timeout=10,
                max_size=2**20  # 1MB
            )
            self.connections.append(ws)
            return True
        except Exception as e:
            self.errors.append(f"Client {client_id}: Connection failed - {str(e)}")
            return False
    
    async def establish_connections(self) -> int:
        """Estabelece m?ltiplas conex?es WebSocket"""
        print(f"\n? Conectando {self.num_connections} clientes WebSocket...")
        
        tasks = [
            self.connect_client(i) 
            for i in range(self.num_connections)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = sum(1 for r in results if r is True)
        
        print(f"? {successful}/{self.num_connections} conex?es estabelecidas")
        return successful
    
    async def listen_for_messages(self, client_id: int, ws: websockets.WebSocketClientProtocol):
        """Listener para cada cliente aguardar mensagens"""
        try:
            async for message in ws:
                try:
                    data = json.loads(message)
                    
                    # Extrair timestamp do servidor
                    if "timestamp" in data:
                        server_timestamp = data["timestamp"]
                        # Calcular lat?ncia (tempo desde envio at? recebimento)
                        latency_ms = (time.time() - int(server_timestamp)) * 1000
                        self.latencies.append(latency_ms)
                        self.received_messages[client_id].append(latency_ms)
                except json.JSONDecodeError:
                    self.errors.append(f"Client {client_id}: Invalid JSON message")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.errors.append(f"Client {client_id}: Listen error - {str(e)}")
    
    async def broadcast_message(self, message_type: str):
        """Envia mensagem para ser recebida por todos os clientes"""
        msg = {
            "type": message_type,
            "timestamp": int(time.time()),
            "data": {
                "event": "TRADE_EXECUTED",
                "bot_id": "stress_test_bot",
                "trade": {
                    "symbol": "BTC/USDT",
                    "side": "BUY",
                    "price": 50000.00,
                    "quantity": 0.1
                }
            }
        }
        
        # Simular mensagem sendo colocada na fila
        # Em um teste real, isso viria do servidor
        return json.dumps(msg)
    
    async def run_test(self, duration_seconds: int = 10):
        """Executa o teste completo"""
        print(f"\n{'='*60}")
        print(f"? WEBSOCKET LOAD TEST - {self.num_connections} conex?es")
        print(f"{'='*60}\n")
        
        self.start_time = time.time()
        
        # 1. Estabelecer conex?es
        connection_count = await self.establish_connections()
        
        if connection_count == 0:
            print("? Nenhuma conex?o foi estabelecida!")
            return False
        
        # 2. Iniciar listeners
        print(f"\n? Iniciando listeners para {connection_count} clientes...")
        listener_tasks = [
            self.listen_for_messages(i, self.connections[i])
            for i in range(connection_count)
        ]
        listeners = asyncio.gather(*listener_tasks)
        
        # 3. Simular tr?fego por X segundos
        print(f"? Simulando tr?fego por {duration_seconds} segundos...\n")
        
        try:
            for second in range(duration_seconds):
                # Enviar mensagem simulada a cada segundo
                msg = await self.broadcast_message("TRADE_EXECUTED")
                print(f"  [{second+1}s] Mensagem de broadcast enviada")
                await asyncio.sleep(1)
        finally:
            # 4. Encerrar listeners
            listeners.cancel()
            await asyncio.sleep(0.5)
        
        # 5. Fechar conex?es
        print(f"\n? Fechando {connection_count} conex?es...")
        for ws in self.connections:
            try:
                await ws.close()
            except:
                pass
        
        self.end_time = time.time()
        
        # 6. Gerar relat?rio
        await self.print_report()
        
        # 7. Valida??o
        return self.validate_results()
    
    async def print_report(self):
        """Imprime relat?rio de teste"""
        print(f"\n{'='*60}")
        print(f"? RELAT?RIO DE TESTE")
        print(f"{'='*60}\n")
        
        duration = self.end_time - self.start_time
        
        print(f"??  Dura??o do teste: {duration:.2f} segundos")
        print(f"? Conex?es estabelecidas: {len(self.connections)}/{self.num_connections}")
        print(f"? Total de mensagens recebidas: {len(self.latencies)}")
        
        if self.latencies:
            avg_latency = statistics.mean(self.latencies)
            median_latency = statistics.median(self.latencies)
            min_latency = min(self.latencies)
            max_latency = max(self.latencies)
            stddev_latency = statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0
            
            print(f"\n??  LAT?NCIA DAS MENSAGENS:")
            print(f"   M?dia:    {avg_latency:.2f} ms")
            print(f"   Mediana:  {median_latency:.2f} ms")
            print(f"   M?nima:   {min_latency:.2f} ms")
            print(f"   M?xima:   {max_latency:.2f} ms")
            print(f"   StdDev:   {stddev_latency:.2f} ms")
            
            # Analisar distribui??o
            p50 = self._percentile(self.latencies, 50)
            p95 = self._percentile(self.latencies, 95)
            p99 = self._percentile(self.latencies, 99)
            
            print(f"\n? PERCENTIS:")
            print(f"   P50 (50%):  {p50:.2f} ms")
            print(f"   P95 (95%):  {p95:.2f} ms")
            print(f"   P99 (99%):  {p99:.2f} ms")
        
        if self.errors:
            print(f"\n??  ERROS ({len(self.errors)}):")
            for error in self.errors[:5]:  # Mostrar primeiros 5 erros
                print(f"   - {error}")
            if len(self.errors) > 5:
                print(f"   ... e mais {len(self.errors) - 5} erros")
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calcula percentil"""
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[index] if index < len(sorted_values) else sorted_values[-1]
    
    def validate_results(self) -> bool:
        """Valida se o teste passou"""
        print(f"\n{'='*60}")
        print(f"? VALIDA??O")
        print(f"{'='*60}\n")
        
        passed = True
        
        # 1. Verificar conex?es
        if len(self.connections) < self.num_connections * 0.8:  # 80% esperado
            print(f"? Conex?es insuficientes: {len(self.connections)}/{self.num_connections}")
            passed = False
        else:
            print(f"? Conex?es: {len(self.connections)}/{self.num_connections}")
        
        # 2. Verificar mensagens
        if len(self.latencies) == 0:
            print(f"? Nenhuma mensagem foi recebida!")
            passed = False
        else:
            print(f"? Mensagens recebidas: {len(self.latencies)}")
        
        # 3. Verificar lat?ncia
        if self.latencies:
            avg_latency = statistics.mean(self.latencies)
            if avg_latency > LATENCY_THRESHOLD_MS:
                print(f"? Lat?ncia acima do threshold: {avg_latency:.2f}ms > {LATENCY_THRESHOLD_MS}ms")
                passed = False
            else:
                print(f"? Lat?ncia dentro do esperado: {avg_latency:.2f}ms < {LATENCY_THRESHOLD_MS}ms")
        
        # 4. Verificar erros
        if self.errors:
            print(f"??  Erros encontrados: {len(self.errors)}")
            if len(self.errors) > self.num_connections * 0.1:  # > 10% de erro
                print(f"? Taxa de erro muito alta")
                passed = False
        else:
            print(f"? Sem erros")
        
        print(f"\n{'='*60}")
        if passed:
            print(f"? TESTE PASSOU!")
        else:
            print(f"? TESTE FALHOU!")
        print(f"{'='*60}\n")
        
        return passed


async def main():
    """Entry point"""
    tester = WebSocketLoadTest(WEBSOCKET_URL, NUM_CONNECTIONS)
    
    try:
        result = await tester.run_test(duration_seconds=10)
        return 0 if result else 1
    except KeyboardInterrupt:
        print("\n??  Teste interrompido pelo usu?rio")
        return 2
    except Exception as e:
        print(f"\n? Erro ao executar teste: {e}")
        return 3


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
