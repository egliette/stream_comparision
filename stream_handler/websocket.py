import asyncio
import uuid

from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect

from utils.fps_logger import FPSLogger
from utils.frame_processor import FrameProcessor
from utils.logger import get_logger

logger = get_logger(__name__)

async def generate_frames(websocket: WebSocket):
    await websocket.accept()
    app_state = websocket.app.state
    
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[WS Client {request_id}] Connected.")
    
    fps_logger = FPSLogger(request_id, window_size=10)
    frame_processor = FrameProcessor(app_state.video_reader, fps_logger)

    try:
        while True:
            server = getattr(app_state, "server", None)
            if server and server.should_exit:
                break

            frame_bytes = await frame_processor.get_encoded_frame()
            
            if frame_bytes is None:
                await asyncio.sleep(0.001)
                continue

            await websocket.send_bytes(frame_bytes)

    except WebSocketDisconnect:
        logger.info(f"[WS Client {request_id}] Disconnected.")
    except Exception as e:
        logger.error(f"[WS Client {request_id}] Error: {e}")
    finally:
        logger.info(f"[WS Client {request_id}] Stream closed.")
