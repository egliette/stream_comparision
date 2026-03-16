import csv
import os
import statistics
import threading
from collections import deque
from datetime import datetime

import psutil

from utils.logger import get_logger
from utils.stats import registry

logger = get_logger(__name__)

class ResourceLogger:
    def __init__(self, log_interval=10, csv_path=None):
        self._log_interval = log_interval
        self._csv_path = csv_path
        self.proc = psutil.Process(os.getpid())
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._cpu_history = deque(maxlen=3600)
        self._ram_history = deque(maxlen=3600)
        self._latest_cpu = 0.0
        self._latest_ram = 0.0

        if self._csv_path:
            with open(self._csv_path, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "cpu_pct", "ram_mb", "threads", "children", "bandwidth_mbps"])

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self):
        while self._running:
            try:
                children = self.proc.children(recursive=True)
                all_procs = [self.proc] + children

                cpu = sum(p.cpu_percent(interval=1) for p in all_procs)
                ram = sum(p.memory_info().rss for p in all_procs) / 1024**2
                self._latest_cpu = cpu
                self._latest_ram = ram
                threads = sum(p.num_threads() for p in all_procs)
                bandwidth_mbps = registry.get_total_bandwidth_mbps()

                self._cpu_history.append(cpu)
                self._ram_history.append(ram)
                
                cpu_avg = statistics.mean(self._cpu_history)
                ram_avg = statistics.mean(self._ram_history)
                
                if len(self._cpu_history) > 1:
                    cpu_q = statistics.quantiles(self._cpu_history, n=100)
                    cpu_p90, cpu_p95 = cpu_q[89], cpu_q[94]
                else:
                    cpu_p90 = cpu_p95 = cpu

                if len(self._ram_history) > 1:
                    ram_q = statistics.quantiles(self._ram_history, n=100)
                    ram_p90, ram_p95 = ram_q[89], ram_q[94]
                else:
                    ram_p90 = ram_p95 = ram
            
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if self._csv_path:
                    with open(self._csv_path, "a", newline="") as f:
                        csv.writer(f).writerow([current_time, cpu, ram, threads, len(children), bandwidth_mbps])
                
                logger.info(
                    f"Resource Usage: \n"
                    f"  CPU: {cpu:.1f}% (Avg: {cpu_avg:.1f}%) | \n"
                    f"  RAM: {ram:.1f}MB (Avg: {ram_avg:.1f}MB) | \n"
                    f"  Bandwidth: {bandwidth_mbps:.2f} Mbps | \n"
                    f"  Clients: {registry.get_active_clients_count()} | \n"
                    f"  Threads: {threads} | Children: {len(children)}"
                )
            except Exception as e:
                logger.error(f"Error logging resources: {e}")
            
            self._stop_event.wait(timeout=self._log_interval)

        logger.info("Stop resource logger")

    def get_latest_resources(self):
        return {
            "cpu": self._latest_cpu,
            "ram": self._latest_ram
        }