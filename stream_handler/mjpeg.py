import asyncio
import uuid

from fastapi import Request

from utils.fps_logger import FPSLogger
from utils.frame_processor import FrameProcessor
from utils.logger import get_logger

logger = get_logger(__name__)

async def generate_frames(request: Request):
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[Client {request_id}] Client connected.")

    app_state = request.app.state
    fps_logger = FPSLogger(request_id, window_size=10)
    frame_processor = FrameProcessor(app_state.video_reader, fps_logger)

    try:
        while True:
            server = getattr(app_state, "server", None)
            if server and server.should_exit:
                break

            if await request.is_disconnected():
                logger.info(f"[Client {request_id}] Client disconnected.")
                break

            frame_bytes = await frame_processor.get_encoded_frame()
            if frame_bytes is None:
                await asyncio.sleep(0.001)
                continue

            # Bandwidth for each frame = 0.67 MB
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    except asyncio.CancelledError:
        raise  # re-raise so uvicorn can clean up the request properly
    finally:
        logger.info(f"[Client {request_id}] Stream closed.")
