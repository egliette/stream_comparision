from dataclasses import dataclass, field
import threading
from typing import Dict
from utils.bandwidth_tracker import BandwidthTracker

@dataclass
class ClientStats:
    bandwidth: BandwidthTracker = field(default_factory=BandwidthTracker)
    fps: float = 0.0
    latency_ms: float = 0.0

class StatsRegistry:
    def __init__(self):
        self._clients: Dict[str, ClientStats] = {}
        self._lock = threading.Lock()

    def get_client(self, client_id: str) -> ClientStats:
        with self._lock:
            if client_id not in self._clients:
                self._clients[client_id] = ClientStats()
            return self._clients[client_id]

    def remove_client(self, client_id: str):
        with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]

    def get_total_bandwidth_mbps(self) -> float:
        with self._lock:
            return sum(c.bandwidth.get_bandwidth_mbps() for c in self._clients.values())

    def get_total_bandwidth_byte_rate(self) -> float:
        with self._lock:
            return sum(c.bandwidth.get_bandwidth_byte_rate() for c in self._clients.values())

    def get_total_mb(self) -> float:
        with self._lock:
            return sum(c.bandwidth.get_total_mb() for c in self._clients.values())

    def get_max_fps(self) -> float:
        with self._lock:
            if not self._clients: return 0.0
            return max(c.fps for c in self._clients.values())

    def get_avg_latency(self) -> float:
        with self._lock:
            if not self._clients: return 0.0
            return sum(c.latency_ms for c in self._clients.values()) / len(self._clients)

    def get_active_clients_count(self) -> int:
        with self._lock:
            return len(self._clients)

# Global registry
registry = StatsRegistry()
