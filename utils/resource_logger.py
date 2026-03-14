import csv
import logging
import os
import threading
from datetime import datetime

import psutil

from utils.logger import get_logger

logger = get_logger(__name__)

class ResourceLogger:
    def __init__(self, log_interval=10, csv_path=None):
        self._log_interval = log_interval
        self._csv_path = csv_path
        self.proc = psutil.Process(os.getpid())
        self._running = False
        self._thread = None
        self._stop_event = threading.Event()  # <-- add this

        if self._csv_path:
            with open(self._csv_path, "w", newline="") as f:
                csv.writer(f).writerow(["timestamp", "cpu_pct", "ram_mb", "threads", "children"])

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()  # wake up the sleeping thread immediately
        if self._thread and self._thread.is_alive():
            self._thread.join()

    def _run(self):
        while self._running:
            try:
                children = self.proc.children(recursive=True)
                all_procs = [self.proc] + children

                cpu = sum(p.cpu_percent(interval=1) for p in all_procs)
                ram = sum(p.memory_info().rss for p in all_procs) / 1024**2
                threads = sum(p.num_threads() for p in all_procs)
            
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if self._csv_path:
                    with open(self._csv_path, "a", newline="") as f:
                        csv.writer(f).writerow([current_time, cpu, ram, threads, len(children)])
                
                logger.info(f"Resource Usage: CPU: {cpu:.1f}%, RAM: {ram:.1f}MB, Threads: {threads}, Children: {len(children)}") 
            except Exception as e:
                logger.error(f"Error logging resources: {e}")

            # Instead of time.sleep(N), wait on the event with a timeout
            # If stop() is called, the event fires and we exit immediately
            self._stop_event.wait(timeout=self._log_interval)