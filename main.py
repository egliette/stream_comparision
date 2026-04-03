import argparse
import yaml
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from stream_handler import webrtc
from stream_handler.mjpeg import generate_frames as mjpeg_generate_frames
from stream_handler.websocket import generate_frames as websocket_generate_frames
from utils.logger import get_logger
from utils.resource_logger import ResourceLogger
from utils.stats import registry
from utils.video_reader import BackgroundVideoReader

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    res_logger = ResourceLogger(log_interval=10)
    res_logger.start()
    app.state.res_logger = res_logger

    app.state.video_readers = {}
    try:
        with open("cameras.yaml", "r") as f:
            cameras = yaml.safe_load(f)
            if not cameras:
                cameras = {}
    except FileNotFoundError:
        logger.warning("cameras.yaml not found, no streams initialized.")
        cameras = {}

    for stream_id, rtsp_url in cameras.items():
        logger.info(f"Initializing stream {stream_id} with url {rtsp_url}")
        video_reader = BackgroundVideoReader(rtsp_url)
        video_reader.start()
        app.state.video_readers[stream_id] = video_reader

    app.state.pcs = set()

    try:
        yield
    finally:
        logger.info("Closing server")
        for pc in list(app.state.pcs):
            await pc.close()
        
        for reader in app.state.video_readers.values():
            reader.stop()
        res_logger.stop()

app = FastAPI(title="Simple Video Stream", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws/{stream_id}")
async def websocket_stream(websocket: WebSocket, stream_id: str):
    if stream_id not in websocket.app.state.video_readers:
        await websocket.close(code=1008)
        return
    await websocket_generate_frames(websocket, stream_id)

@app.get("/mjpeg_stream/{stream_id}")
async def mjpeg_stream(request: Request, stream_id: str):
    if stream_id not in request.app.state.video_readers:
        raise HTTPException(status_code=404, detail="Stream not found")
    return StreamingResponse(mjpeg_generate_frames(request, stream_id),
                             media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/offer/{stream_id}")
async def webrtc_offer(request: Request, stream_id: str):
    if stream_id not in request.app.state.video_readers:
        raise HTTPException(status_code=404, detail="Stream not found")
    params = await request.json()
    video_reader = request.app.state.video_readers[stream_id]
    pcs = request.app.state.pcs
    return await webrtc.offer(params, video_reader, pcs)

@app.get("/stats")
async def get_stats(request: Request):
    res_stats = request.app.state.res_logger.get_latest_resources()
    return {
        "clients": registry.get_active_clients_count(),
        "total_bandwidth_mbps": registry.get_total_bandwidth_mbps(),
        "total_bandwidth_mb": registry.get_total_mb(),
        "fps": registry.get_max_fps(),
        "latency": registry.get_avg_latency(),
        "cpu": res_stats["cpu"],
        "ram": res_stats["ram"]
    }

@app.get("/")
async def root():
    return RedirectResponse(url="/mjpeg/stream_1")

@app.get("/mjpeg/{stream_id}")
@app.get("/websocket/{stream_id}")
@app.get("/webrtc/{stream_id}")
async def index(stream_id: str):
    return FileResponse("static/index.html")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", "-H", type=str, default="0.0.0.0")
    parser.add_argument("--port", "-p", type=int, default=8000)
    
    args = parser.parse_args()
    
    logger.info(f"Server accessible at: http://{args.host}:{args.port}/")
    
    config = uvicorn.Config(app, host=args.host, port=args.port)
    server = uvicorn.Server(config)
    app.state.server = server
    try:
        server.run()
    except KeyboardInterrupt:
        pass