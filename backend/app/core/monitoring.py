"""
? Resource Monitor - Crypto Trade Hub
Monitora uso de mem?ria (RSS) e CPU a cada 60 segundos

Integra??o com main.py:
  from app.core.monitoring import resource_monitor
  
  # Na fun??o on_startup:
  await resource_monitor.start()
  
  # Na fun??o on_shutdown:
  await resource_monitor.stop()
"""

import asyncio
import psutil
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """Snapshot de recursos em um momento espec?fico"""
    timestamp: datetime
    memory_rss_mb: float  # Resident Set Size em MB
    memory_percent: float  # Porcentagem da RAM usada pelo processo
    cpu_percent: float    # Porcentagem de CPU
    num_threads: int      # N?mero de threads
    num_fds: int          # Number of file descriptors (conex?es abertas)


class ResourceMonitor:
    """Monitora recursos do sistema em intervalo regular"""
    
    def __init__(self, interval_seconds: int = 60, enabled: bool = True):
        self.interval = interval_seconds
        self.enabled = enabled
        self.snapshots: List[ResourceSnapshot] = []
        self.process = psutil.Process(os.getpid())
        self.monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Inicia monitoramento em background"""
        if not self.enabled:
            logger.info("Resource monitoring is DISABLED")
            return
        
        logger.info(f"Starting resource monitor (interval: {self.interval}s)")
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop(self):
        """Para o monitoramento"""
        if not self.enabled:
            return
        
        logger.info("Stopping resource monitor")
        self.monitoring = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        # Imprimir sum?rio final
        self._print_final_report()
    
    async def _monitor_loop(self):
        """Loop de monitoramento"""
        try:
            while self.monitoring:
                snapshot = self._take_snapshot()
                self.snapshots.append(snapshot)
                self._log_snapshot(snapshot)
                
                await asyncio.sleep(self.interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
    
    def _take_snapshot(self) -> ResourceSnapshot:
        """Captura snapshot actual de recursos"""
        try:
            memory_info = self.process.memory_info()
            memory_rss_mb = memory_info.rss / (1024 * 1024)  # Converter para MB
            
            memory_percent = self.process.memory_percent()
            cpu_percent = self.process.cpu_percent(interval=1)
            num_threads = self.process.num_threads()
            
            # N?mero de file descriptors (aproximado como n?mero de conex?es)
            try:
                num_fds = len(self.process.open_files())
            except (AttributeError, OSError):
                num_fds = 0
            
            return ResourceSnapshot(
                timestamp=datetime.utcnow(),
                memory_rss_mb=memory_rss_mb,
                memory_percent=memory_percent,
                cpu_percent=cpu_percent,
                num_threads=num_threads,
                num_fds=num_fds
            )
        except Exception as e:
            logger.error(f"Error taking snapshot: {e}")
            return ResourceSnapshot(
                timestamp=datetime.utcnow(),
                memory_rss_mb=0,
                memory_percent=0,
                cpu_percent=0,
                num_threads=0,
                num_fds=0
            )
    
    def _log_snapshot(self, snapshot: ResourceSnapshot):
        """Log de snapshot com formata??o"""
        log_msg = (
            f"? RECURSOS | "
            f"Mem?ria: {snapshot.memory_rss_mb:.1f}MB ({snapshot.memory_percent:.1f}%) | "
            f"CPU: {snapshot.cpu_percent:.1f}% | "
            f"Threads: {snapshot.num_threads} | "
            f"Conex?es: {snapshot.num_fds}"
        )
        logger.info(log_msg)
    
    def _print_final_report(self):
        """Imprime relat?rio final de monitoramento"""
        if not self.snapshots:
            return
        
        print("\n" + "="*70)
        print("? RELAT?RIO FINAL - RECURSOS DO SISTEMA")
        print("="*70 + "\n")
        
        # Primeira e ?ltima captura
        first = self.snapshots[0]
        last = self.snapshots[-1]
        
        print(f"??  Per?odo de monitoramento:")
        print(f"   In?cio: {first.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Fim:    {last.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Dura??o: {(last.timestamp - first.timestamp).total_seconds():.0f} segundos")
        
        # Estat?sticas de mem?ria
        mem_values = [s.memory_rss_mb for s in self.snapshots]
        print(f"\n? MEM?RIA (RSS):")
        print(f"   Inicial:  {first.memory_rss_mb:.1f} MB")
        print(f"   Atual:    {last.memory_rss_mb:.1f} MB")
        print(f"   M?nima:   {min(mem_values):.1f} MB")
        print(f"   M?xima:   {max(mem_values):.1f} MB")
        print(f"   M?dia:    {sum(mem_values)/len(mem_values):.1f} MB")
        print(f"   Varia??o: {last.memory_rss_mb - first.memory_rss_mb:+.1f} MB")
        
        # Verificar vazamento de mem?ria
        if last.memory_rss_mb > first.memory_rss_mb * 1.5:
            print(f"   ??  POSS?VEL VAZAMENTO DE MEM?RIA (crescimento > 50%)")
        elif last.memory_rss_mb > first.memory_rss_mb * 1.1:
            print(f"   ??  Crescimento moderado de mem?ria (10-50%)")
        else:
            print(f"   ? Mem?ria est?vel")
        
        # Estat?sticas de CPU
        cpu_values = [s.cpu_percent for s in self.snapshots]
        print(f"\n??  CPU:")
        print(f"   M?dia:    {sum(cpu_values)/len(cpu_values):.1f}%")
        print(f"   M?xima:   {max(cpu_values):.1f}%")
        print(f"   M?nima:   {min(cpu_values):.1f}%")
        
        # Estat?sticas de threads
        thread_values = [s.num_threads for s in self.snapshots]
        print(f"\n? THREADS:")
        print(f"   Inicial:  {first.num_threads}")
        print(f"   M?xima:   {max(thread_values)}")
        print(f"   Atual:    {last.num_threads}")
        
        # Estat?sticas de conex?es
        fds_values = [s.num_fds for s in self.snapshots]
        print(f"\n? CONEX?ES ABERTAS (FD):")
        print(f"   Inicial:  {first.num_fds}")
        print(f"   M?xima:   {max(fds_values)}")
        print(f"   Atual:    {last.num_fds}")
        
        # Recomenda??es
        print(f"\n? RECOMENDA??ES:")
        avg_memory = sum(mem_values) / len(mem_values)
        if avg_memory > 500:
            print(f"   ??  Consumo alto de mem?ria (m?dia > 500MB)")
        
        if max(cpu_values) > 80:
            print(f"   ??  Picos de CPU > 80%")
        
        if max(thread_values) > 100:
            print(f"   ??  Muitas threads ({max(thread_values)} > 100)")
        
        if max(fds_values) > 1000:
            print(f"   ??  Muitas conex?es ({max(fds_values)} > 1000)")
        
        if (last.memory_rss_mb - first.memory_rss_mb) / first.memory_rss_mb > 0.5:
            print(f"   ??  Poss?vel vazamento de mem?ria detectado")
        
        print("\n" + "="*70 + "\n")
    
    def get_current_snapshot(self) -> ResourceSnapshot:
        """Retorna snapshot atual"""
        return self._take_snapshot()
    
    def get_stats(self) -> Dict:
        """Retorna dicion?rio com estat?sticas"""
        if not self.snapshots:
            return {}
        
        mem_values = [s.memory_rss_mb for s in self.snapshots]
        cpu_values = [s.cpu_percent for s in self.snapshots]
        
        return {
            "snapshots_count": len(self.snapshots),
            "duration_seconds": (
                self.snapshots[-1].timestamp - self.snapshots[0].timestamp
            ).total_seconds(),
            "memory": {
                "initial_mb": self.snapshots[0].memory_rss_mb,
                "current_mb": self.snapshots[-1].memory_rss_mb,
                "min_mb": min(mem_values),
                "max_mb": max(mem_values),
                "avg_mb": sum(mem_values) / len(mem_values),
                "growth_mb": self.snapshots[-1].memory_rss_mb - self.snapshots[0].memory_rss_mb
            },
            "cpu": {
                "avg_percent": sum(cpu_values) / len(cpu_values),
                "max_percent": max(cpu_values),
                "min_percent": min(cpu_values)
            },
            "threads": {
                "initial": self.snapshots[0].num_threads,
                "current": self.snapshots[-1].num_threads,
                "max": max(s.num_threads for s in self.snapshots)
            },
            "connections": {
                "initial": self.snapshots[0].num_fds,
                "current": self.snapshots[-1].num_fds,
                "max": max(s.num_fds for s in self.snapshots)
            }
        }


# Inst?ncia global
resource_monitor = ResourceMonitor(interval_seconds=60, enabled=True)
