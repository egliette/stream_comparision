import asyncio
import time
from fractions import Fraction

import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame

from utils.video_reader import BackgroundVideoReader
import uuid
from utils.stats import registry
from utils.fps_logger import FPSLogger



from utils.logger import get_logger

logger = get_logger(__name__)

VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = Fraction(1, VIDEO_CLOCK_RATE)


class VideoStreamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, video_reader: BackgroundVideoReader, client_id: str):
        super().__init__()
        self.video_reader = video_reader
        self.client_id = client_id
        self._start_time: float | None = None
        self._timestamp = 0
        self.client_stats = registry.get_client(client_id)
        self.fps_logger = FPSLogger(client_id, window_size=10)

    async def recv(self):
        current_time = time.time()
        self.fps_logger.log_frame(current_time)
        self.client_stats.fps = self.fps_logger.get_fps()
        
        fps = self.video_reader.fps
        pts_increment = int(VIDEO_CLOCK_RATE / fps)

        if self._start_time is None:
            self._start_time = time.time()
        else:
            self._timestamp += pts_increment

        # Throttle to match source FPS
        expected = self._start_time + self._timestamp / VIDEO_CLOCK_RATE
        delay = expected - time.time()
        if delay > 0:
            await asyncio.sleep(delay)

        latest = self.video_reader.get_latest_frame()

        if latest is None:
            logger.warning("No frame available from reader, sending black frame")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            timestamp = time.time()
        else:
            frame_id, timestamp, frame = latest
    
        # Track processing latency
        self.client_stats.latency_ms = (time.time() - timestamp) * 1000
        
        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = self._timestamp
        new_frame.time_base = VIDEO_TIME_BASE

        # Rough estimate of bandwidth (raw frame size)
        # Note: Actual bandwidth depends on encoder (VP8/H264)
        self.client_stats.bandwidth.add_bytes(frame.nbytes)

        return new_frame

async def offer(request_data: dict, video_reader: BackgroundVideoReader, pcs: set):
    offer_sdp = RTCSessionDescription(sdp=request_data["sdp"], type=request_data["type"])
    client_id = str(uuid.uuid4())[:8]

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)
            registry.remove_client(client_id)

    pc.addTrack(VideoStreamTrack(video_reader, client_id))
    await pc.setRemoteDescription(offer_sdp)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Wait for ICE gathering to complete so the SDP contains candidates
    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.01)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }
