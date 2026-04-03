# WebRTC Video Streaming Guide

This guide explains how to implement **WebRTC** streaming. WebRTC is the gold standard for low-latency, real-time communication, but it requires more setup (Signaling and Peer Connections) than MJPEG or WebSockets.

---

## 1. Prerequisites
You need the `aiortc` library for handling WebRTC in Python.

```bash
pip install aiortc
```

Update your `requirements.txt`:
```text
aiortc==1.9.0
```

---

## 2. Implementation: WebRTC Service
Create `stream_handler/webrtc.py`. Unlike MJPEG/WS which push frames, WebRTC uses a **MediaStreamTrack**.

```python
import asyncio
import json
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame
import cv2
import numpy as np

class VideoStreamTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, video_reader):
        super().__init__()
        self.video_reader = video_reader

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        # Get latest frame from our shared reader
        latest = self.video_reader.get_latest_frame()
        if latest is None:
            # Fallback for sync
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
        else:
            id, frame = latest

        # Convert to PyAV frame
        new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        new_frame.pts = pts
        new_frame.time_base = time_base
        return new_frame

async def offer(request_data, video_reader):
    params = request_data
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState == "failed":
            await pc.close()

    # Add our custom video track
    pc.addTrack(VideoStreamTrack(video_reader))

    # Handle the offer and create an answer
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    }
```

---

## 3. Integration in `main.py`
You need a POST endpoint for the WebRTC "Signaling" (exchanging connection details).

```python
from stream_handler import webrtc

@app.post("/offer")
async def webrtc_offer(request: Request):
    params = await request.json()
    video_reader = request.app.state.video_reader
    answer = await webrtc.offer(params, video_reader)
    return answer

@app.get("/webrtc")
async def webrtc_page():
    return FileResponse("static/index.html")
```

---

## 4. Frontend Logic
WebRTC requires a complex handshake. Update your `static/stream.js` to handle the peer connection.

### 4.1. HTML Update (`static/index.html`)

You need to update your `<main>` section to include a `<video>` tag and toggle its visibility depending on the stream type.

```html
<main>
    <!-- Used for MJPEG and WebSocket -->
    <img id="stream" src="" />
    
    <!-- Used for WebRTC -->
    <video id="web-video" class="hidden" autoplay playsinline></video>
</main>
```

### 4.2. CSS Update (`static/style.css`)

Instead of using inline styles, add these rules to your stylesheet to handle the video layout and hiding:

```css
img, video {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

.hidden {
    display: none !important;
}
```

### JavaScript Update (`static/stream.js`)
```javascript
async function startWebRTC() {
    const pc = new RTCPeerConnection();
    const video = document.getElementById('web-video');

    // Handle incoming track
    pc.ontrack = (event) => {
        video.srcObject = event.streams[0];
    };

    // Add a dummy transceiver to trigger video stream
    pc.addTransceiver('video', { direction: 'recvonly' });

    // Create Offer
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // Send Offer to server (Signaling)
    const response = await fetch('/offer', {
        method: 'POST',
        body: JSON.stringify({
            sdp: pc.localDescription.sdp,
            type: pc.localDescription.type
        }),
        headers: { 'Content-Type': 'application/json' }
    });

    // Handle Answer
    const answer = await response.json();
    await pc.setRemoteDescription(new RTCSessionDescription(answer));
}
```

---

## 5. Performance Note
WebRTC provides the **lowest latency** (sub-100ms) but uses significantly more CPU than WebSockets or MJPEG because it must perform complex handshakes, encryption (DTLS/SRTP), and real-time VP8/H264 encoding per peer.

For your "Shared Encoding" optimization to work perfectly here, you would need to implement a **Broadcaster** pattern where the server encodes only once and forwards the RTP packets to all peers, which is significantly more advanced.
