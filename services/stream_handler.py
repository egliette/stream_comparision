import asyncio
import time
import uuid

import cv2
from fastapi import Request

from utils.logger import get_logger

logger = get_logger(__name__)

async def generate_frames(request: Request, shutdown_event: asyncio.Event):
    reader = request.app.state.video_reader
    frame_delay = 1.0 / reader.fps

    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[Client {request_id}] Client connected.")

    frames_sent = 0
    last_log_time = time.time()

    try:
        while not shutdown_event.is_set():
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

            frames_sent += 1
            current_time = time.time()
            elapsed = current_time - last_log_time
            if elapsed >= 10.0:
                fps = frames_sent / elapsed
                logger.info(f"[Client {request_id}] Streaming at {fps:.2f} FPS")
                frames_sent = 0
                last_log_time = current_time

            # Sleep for frame_delay, but wake up early if shutdown is triggered
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=frame_delay)
            except asyncio.TimeoutError:
                pass  # normal case, keep streaming

    except asyncio.CancelledError:
        logger.info(f"[Client {request_id}] Stream cancelled.")
        raise  # re-raise so uvicorn can clean up the request properly
