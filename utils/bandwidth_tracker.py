import time
import threading
from collections import deque

class BandwidthTracker:
    def __init__(self, window_size=1):
        self._total_bytes = 0
        self._bytes_history = deque()  # list of (timestamp, bytes)
        self._window_size = window_size
        self._lock = threading.Lock()

    def add_bytes(self, count: int):
        with self._lock:
            now = time.time()
            self._total_bytes += count
            self._bytes_history.append((now, count))
            self._cleanup(now)

    def _cleanup(self, now: float):
        while self._bytes_history and self._bytes_history[0][0] < now - self._window_size:
            self._bytes_history.popleft()

    def get_bandwidth_mbps(self) -> float:
        """Returns current bandwidth in Megabits per second."""
        with self._lock:
            now = time.time()
            self._cleanup(now)
            if not self._bytes_history:
                return 0.0
            total_window_bytes = sum(b for _, b in self._bytes_history)
            # Bytes to Megabits / window_size
            return (total_window_bytes * 8) / (1024 * 1024 * self._window_size)

    def get_total_mb(self) -> float:
        return self._total_bytes / (1024 * 1024)
