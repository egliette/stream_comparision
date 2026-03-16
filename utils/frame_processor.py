import time
import struct

import cv2

from utils.fps_logger import FPSLogger
from utils.video_reader import BackgroundVideoReader


class FrameProcessor:
    def __init__(self, video_reader: BackgroundVideoReader, fps_logger: FPSLogger):
        self._video_reader = video_reader
        self._fps_logger = fps_logger
        self._last_frame_id = -1

    async def get_encoded_frame(self) -> bytes | None:
        latest = self._video_reader.get_latest_frame()
        if latest is None:
            return None
        
        frame_id, capture_time, frame = latest
        if frame_id <= self._last_frame_id:
            return None

        self._last_frame_id = frame_id
        
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            return None

        current_time = time.time()
        self._fps_logger.log_frame(current_time)

        # Prepend timestamp (8-byte float) to the frame bytes
        # Note: This makes the buffer slightly longer. Handlers need to know this.
        # Alternatively, for MJPEG we might NOT want to break the JPEG header for the browser.
        # So let's provide a version with and without metadata.
        return buffer.tobytes(), capture_time

    async def get_encoded_frame_with_timestamp(self) -> bytes | None:
        result = await self.get_encoded_frame()
        if result is None:
            return None
        
        frame_bytes, capture_time = result
        # Pack timestamp as double (8 bytes)
        return struct.pack("!d", capture_time) + frame_bytes