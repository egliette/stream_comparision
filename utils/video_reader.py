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
    def __init__(self, video_path):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            logger.error(f"Error: Could not open video at {self.video_path}")
            self.fps = 30.0
        else:
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30.0

        self.frame_queue = deque(maxlen=int(self.fps))
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
            success, frame = self.cap.read()
            if not success:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                next_frame_time = time.time()
                continue
            
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                self._frame_id += 1
                self.frame_queue.append((self._frame_id, buffer.tobytes()))
            
            next_frame_time += self.frame_delay
            sleep_time = next_frame_time - time.time()
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -1.0:
                next_frame_time = time.time()
                
        logger.info("Stop video reader")

    def get_latest_frame_buffer(self) -> tuple[int, any] | None:
        if len(self.frame_queue) > 0:
            return self.frame_queue[-1]
        return None
