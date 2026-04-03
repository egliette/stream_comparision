import asyncio
import uuid
import time

from fastapi import Request

from utils.fps_logger import FPSLogger
from utils.frame_processor import FrameProcessor
from utils.logger import get_logger

from utils.stats import registry

logger = get_logger(__name__)


async def generate_frames(request: Request, stream_id: str):
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[Client {request_id}] Client connected.")

    app_state = request.app.state
    fps_logger = FPSLogger(request_id, window_size=10)
    frame_processor = FrameProcessor(app_state.video_readers[stream_id], fps_logger)
    client_stats = registry.get_client(request_id)

    try:
        while True:
            server = getattr(app_state, "server", None)
            if server and server.should_exit:
                break

            if await request.is_disconnected():
                logger.info(f"[Client {request_id}] Client disconnected.")
                break

            result = await frame_processor.get_encoded_frame()
            if result is None:
                await asyncio.sleep(0.001)
                continue
            
            frame_bytes, timestamp = result

            # Bandwidth and FPS tracking
            client_stats.fps = fps_logger.get_fps()
            client_stats.latency_ms = (time.time() - timestamp) * 1000
            
            data = (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            client_stats.bandwidth.add_bytes(len(data))
            yield data

    except asyncio.CancelledError:
        raise  # re-raise so uvicorn can clean up the request properly
    finally:
        registry.remove_client(request_id)
        logger.info(f"[Client {request_id}] Stream closed.")
