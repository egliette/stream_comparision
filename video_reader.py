import threading
import time
from collections import deque

import cv2


class BackgroundVideoReader:
    """
    Reads video frames in a background thread and stores them in a fixed-size queue
    to decouple frame capture from stream transmission.
    """
    def __init__(self, video_path, shutdown_event):
        self.video_path = video_path
        self.shutdown_event = shutdown_event
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"Error: Could not open video at {self.video_path}")
            self.fps = 30.0
        else:
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30.0

        # Queue with maxsize equal to video FPS
        self.frame_queue = deque(maxlen=int(self.fps))
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
            self.thread.join()
        if self.cap:
            self.cap.release()

    def _run(self):
        while self.running and not self.shutdown_event.is_set():
             success, frame = self.cap.read()
             if not success:
                 self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                 continue
             
             self.frame_queue.append(frame)
             # Mimic the video's original FPS
             time.sleep(self.frame_delay)

    def get_latest_frame(self):
        # Just read the latest frame without popping
        if len(self.frame_queue) > 0:
            return self.frame_queue[-1]
        return None
