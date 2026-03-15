import time

from utils.fps_logger import FPSLogger
from utils.video_reader import BackgroundVideoReader


class FrameProcessor:
    def __init__(self, video_reader: BackgroundVideoReader, fps_logger: FPSLogger):
        self._video_reader = video_reader
        self._fps_logger = fps_logger
        self._last_frame_id = -1

    async def get_encoded_frame(self) -> bytes | None:
        latest = self._video_reader.get_latest_frame_buffer()
        if latest is None:
            return None
        
        frame_id, encoded_bytes = latest
        if frame_id <= self._last_frame_id:
            return None

        self._last_frame_id = frame_id
        current_time = time.time()
        self._fps_logger.log_frame(current_time)

        return encoded_bytes