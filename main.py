import argparse
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from stream_handler.mjpeg import generate_frames as mjpeg_generate_frames
from stream_handler.websocket import generate_frames as websocket_generate_frames
from utils.logger import get_logger
from utils.resource_logger import ResourceLogger
from utils.video_reader import BackgroundVideoReader

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    res_logger = ResourceLogger(log_interval=10)
    res_logger.start()

    video_reader = BackgroundVideoReader(app.state.video_path)
    video_reader.start()
    app.state.video_reader = video_reader

    try:
        yield
    finally:
        logger.info("Closing server")
        video_reader.stop()
        res_logger.stop()

app = FastAPI(title="Simple Video Stream", lifespan=lifespan)
app.state.video_path = "videos/street.mp4"
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    await websocket_generate_frames(websocket)

@app.get("/mjpeg_stream")
async def mjpeg_stream(request: Request):
    return StreamingResponse(mjpeg_generate_frames(request),
                             media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/")
async def root():
    return RedirectResponse(url="/mjpeg")

@app.get("/mjpeg")
@app.get("/websocket")
async def index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", "-v", type=str, default="videos/street.mp4")
    parser.add_argument("--host", "-H", type=str, default="0.0.0.0")
    parser.add_argument("--port", "-p", type=int, default=8000)
    
    args = parser.parse_args()
    app.state.video_path = args.video
    
    logger.info(f"Server accessible at: http://{args.host}:{args.port}/")
    
    config = uvicorn.Config(app, host=args.host, port=args.port)
    server = uvicorn.Server(config)
    app.state.server = server
    try:
        server.run()
    except KeyboardInterrupt:
        pass