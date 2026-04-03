import threading
import time
from collections import deque

import cv2

from utils.logger import get_logger

logger = get_logger(__name__)

class BackgroundVideoReader:
    """
    Reads video frames in a background thread and stores them in a fixed-size queue
    to decouple frame capture from stream transmission.
    """
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.cap = cv2.VideoCapture(self.rtsp_url)
        if not self.cap.isOpened():
            logger.error(f"Error: Could not open stream at {self.rtsp_url}")
            self.fps = 30.0
        else:
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0 or self.fps > 120:
                self.fps = 30.0

        self.frame_queue = deque(maxlen=1)
        self._frame_id = 0
        self.running = False
        self.thread = None
        self.frame_delay = 1.0 / self.fps

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        if self.cap:
            self.cap.release()

    def _run(self):
        next_frame_time = time.time()
        
        while self.running:
            if not self.cap.isOpened():
                time.sleep(1)
                self.cap = cv2.VideoCapture(self.rtsp_url)
                continue

            success, frame = self.cap.read()
            if not success:
                logger.warning(f"Failed to read frame from {self.rtsp_url}, reconnecting...")
                self.cap.release()
                time.sleep(1)
                continue
            
            self._frame_id += 1
            capture_time = time.time()
            self.frame_queue.append((self._frame_id, capture_time, frame.copy()))
            
            # Read as fast as possible for real-time RTSP or let cv2 handle timing
            # If the RTSP stream controls timing, cap.read() blocks appropriately.
            # But just in case, we can yield slightly to avoid pegging CPU if it's too fast.
            time.sleep(0.001)
                
        logger.info("Stop video reader")

    def get_latest_frame(self) -> tuple[int, float, any] | None:
        if len(self.frame_queue) > 0:
            return self.frame_queue[-1]
        return None
