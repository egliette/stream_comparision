import statistics
import time
from collections import deque

from utils.logger import get_logger

logger = get_logger(__name__)

class FPSLogger:
    def __init__(self, request_id, window_size=10, history_maxlen=3600):
        self.request_id = request_id
        self.window_size = window_size
        self._frame_timestamps = deque(maxlen=window_size * 20) # Buffer for window calculation
        self._fps_history = deque(maxlen=history_maxlen)
        self._last_log_time = time.time()

    def log_frame(self, current_time):
        self._frame_timestamps.append(current_time)
        
        # Log every window_size seconds (approximately)
        if current_time - self._last_log_time >= self.window_size:
            fps = self._calculate_current_fps()
            self._fps_history.append(fps)
            
            avg_fps = statistics.mean(self._fps_history)
            
            if len(self._fps_history) > 1:
                q = statistics.quantiles(self._fps_history, n=100)
                p90, p95 = q[89], q[94]
            else:
                p90 = p95 = fps
                
            logger.info(
                f"[Client {self.request_id}] FPS: {fps:.2f} "
                f"(Avg: {avg_fps:.2f}, p90: {p90:.2f}, p95: {p95:.2f})"
            )
            self._last_log_time = current_time

    def _calculate_current_fps(self):
        if len(self._frame_timestamps) < 2:
            return 0.0
        
        # Calculate FPS based on the frames within the last window_size seconds
        now = self._frame_timestamps[-1]
        start_time = now - self.window_size
        
        # Find frames within the window
        frames_in_window = [t for t in self._frame_timestamps if t >= start_time]
        
        if len(frames_in_window) < 2:
            return 0.0
            
        elapsed = frames_in_window[-1] - frames_in_window[0]
        return (len(frames_in_window) - 1) / elapsed if elapsed > 0 else 0.0
