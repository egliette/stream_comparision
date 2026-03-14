import argparse
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from services.stream_handler import generate_frames
from utils.logger import get_logger
from utils.resource_logger import ResourceLogger
from utils.video_reader import BackgroundVideoReader

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

@app.get("/")
async def video_feed(request: Request):
    return StreamingResponse(generate_frames(request, shutdown_event),
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