import asyncio
import time
import uuid

import cv2
from fastapi import Request

from utils.fps_logger import FPSLogger
from utils.logger import get_logger
from utils.video_reader import BackgroundVideoReader

logger = get_logger(__name__)

async def generate_frames(request: Request):
    reader: BackgroundVideoReader = request.app.state.video_reader
    frame_delay = 1.0 / reader.fps

    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[Client {request_id}] Client connected.")

    fps_logger = FPSLogger(request_id, window_size=10)

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
            fps_logger.log_frame(current_time)

            await asyncio.sleep(frame_delay)

    except asyncio.CancelledError:
        raise  # re-raise so uvicorn can clean up the request properly
    finally:
        logger.info(f"[Client {request_id}] Stream closed.")
