import asyncio
import uuid
import time
import struct

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from utils.fps_logger import FPSLogger
from utils.frame_processor import FrameProcessor
from utils.logger import get_logger
from utils.stats import registry

logger = get_logger(__name__)

async def generate_frames(websocket: WebSocket):
    await websocket.accept()
    app_state = websocket.app.state

    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[WS Client {request_id}] Connected.")

    fps_logger = FPSLogger(request_id, window_size=10)
    frame_processor = FrameProcessor(app_state.video_reader, fps_logger)
    client_stats = registry.get_client(request_id)

    try:
        while True:
            server = getattr(app_state, "server", None)
            if server and server.should_exit:
                break

            result = await frame_processor.get_encoded_frame()
            
            if result is None:
                await asyncio.sleep(0.001)
                continue

            frame_bytes, capture_time = result
            client_stats.fps = fps_logger.get_fps()
            client_stats.latency_ms = (time.time() - capture_time) * 1000
            
            # Prepend timestamp for client-side latency calculation
            frame_data = struct.pack("!d", capture_time) + frame_bytes
            
            client_stats.bandwidth.add_bytes(len(frame_data))
            await websocket.send_bytes(frame_data)

    except WebSocketDisconnect:
        logger.info(f"[WS Client {request_id}] Disconnected.")
    except Exception as e:
        logger.error(f"[WS Client {request_id}] Error: {e}")
    finally:
        registry.remove_client(request_id)
        logger.info(f"[WS Client {request_id}] Stream closed.")
