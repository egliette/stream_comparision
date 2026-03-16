import asyncio
import time
from fractions import Fraction

import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame

from utils.video_reader import BackgroundVideoReader


from utils.logger import get_logger

logger = get_logger(__name__)

VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = Fraction(1, VIDEO_CLOCK_RATE)


class VideoStreamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, video_reader: BackgroundVideoReader):
        super().__init__()
        self.video_reader = video_reader
        self._start_time: float | None = None
        self._timestamp = 0

    async def recv(self):
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
        else:
            _, frame = latest
    
        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = self._timestamp
        new_frame.time_base = VIDEO_TIME_BASE

        return new_frame

async def offer(request_data: dict, video_reader: BackgroundVideoReader, pcs: set):
    offer_sdp = RTCSessionDescription(sdp=request_data["sdp"], type=request_data["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)

    pc.addTrack(VideoStreamTrack(video_reader))
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
