import argparse
import asyncio
import time
import uuid
from contextlib import asynccontextmanager

import cv2
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from logger import get_logger
from resource_logger import ResourceLogger
from video_reader import BackgroundVideoReader

logger = get_logger(__name__)

shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    res_logger = ResourceLogger(log_interval=10)
    res_logger.start()

    # Start the video reader background thread
    video_reader = BackgroundVideoReader(app.state.video_path, shutdown_event)
    video_reader.start()
    app.state.video_reader = video_reader

    try:
        yield
    finally:
        video_reader.stop()
        res_logger.stop()

app = FastAPI(title="Simple Video Stream", lifespan=lifespan)
app.state.video_path = "videos/street.mp4"

async def generate_frames(request: Request):
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

@app.get("/")
async def video_feed(request: Request):
    return StreamingResponse(generate_frames(request),
                             media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serve a video file over HTTP as an MJPEG stream.")
    parser.add_argument("--video", "-v", type=str, default="videos/street.mp4")
    parser.add_argument("--host", "-H", type=str, default="0.0.0.0")
    parser.add_argument("--port", "-p", type=int, default=8000)
    
    args = parser.parse_args()
    app.state.video_path = args.video
    
    print(f"Starting server...")
    print(f"Streaming video: {args.video}")
    print(f"Server accessible at: http://{args.host}:{args.port}/")
    
    config = uvicorn.Config(app, host=args.host, port=args.port)
    server = uvicorn.Server(config)
    app.state.server = server
    try:
        server.run()
    except KeyboardInterrupt:
        pass