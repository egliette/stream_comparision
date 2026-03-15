import asyncio
import time
import uuid
from collections import deque

import cv2
from fastapi import Request

from utils.logger import get_logger
from utils.video_reader import BackgroundVideoReader

logger = get_logger(__name__)

async def generate_frames(request: Request):
    reader: BackgroundVideoReader = request.app.state.video_reader
    frame_delay = 1.0 / reader.fps

    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[Client {request_id}] Client connected.")

    frame_timestamps = deque(maxlen=int(reader.fps * 10))
    last_log_time = time.time()

    try:
        while True:
            server = getattr(request.app.state, "server", None)
            if server and server.should_exit:
                break

            if await request.is_disconnected():
                logger.info(f"[Client {request_id}] Client disconnected.")
                break

            frame = reader.get_latest_frame()
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                await asyncio.sleep(0.01)
                continue

            frame_bytes = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            current_time = time.time()
            frame_timestamps.append(current_time)
            
            if current_time - last_log_time >= 10.0:
                if len(frame_timestamps) > 1:
                    window_elapsed = frame_timestamps[-1] - frame_timestamps[0]
                    fps = (len(frame_timestamps) - 1) / window_elapsed if window_elapsed > 0 else 0.0
                else:
                    fps = 0.0
                
                logger.info(f"[Client {request_id}] Streaming at {fps:.2f} FPS")
                last_log_time = current_time

            await asyncio.sleep(frame_delay)

    except asyncio.CancelledError:
        raise  # re-raise so uvicorn can clean up the request properly
    finally:
        logger.info(f"[Client {request_id}] Stream closed.")
