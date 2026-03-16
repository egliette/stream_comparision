const img = document.getElementById('stream');
const video = document.getElementById('web-video');
const streamTitle = document.getElementById('stream-title');
const navMjpeg = document.getElementById('nav-mjpeg');
const navWebsocket = document.getElementById('nav-websocket');
const navWebrtc = document.getElementById('nav-webrtc');

const path = window.location.pathname;
let currentWs = null;
let currentPc = null;

function stopCurrentStream() {
    // Stop MJPEG
    img.src = "";
    img.classList.add('hidden');

    // Stop WebRTC video
    video.srcObject = null;
    video.classList.add('hidden');

    // Stop WebSocket
    if (currentWs) {
        currentWs.close();
        currentWs = null;
    }

    // Stop WebRTC PeerConnection
    if (currentPc) {
        currentPc.close();
        currentPc = null;
    }

    // Clear active states
    [navMjpeg, navWebsocket, navWebrtc].forEach(btn => btn.classList.remove('active'));
}

function startMjpeg() {
    stopCurrentStream();
    streamTitle.textContent = "MJPEG Stream";
    navMjpeg.classList.add('active');
    img.classList.remove('hidden');
    img.src = "/mjpeg_stream";
}

function startWebsocket() {
    stopCurrentStream();
    streamTitle.textContent = "WebSocket Stream";
    navWebsocket.classList.add('active');
    img.classList.remove('hidden');

    const ws = new WebSocket(`ws://${location.host}/ws`);
    ws.binaryType = 'blob';
    currentWs = ws;

    ws.onmessage = (event) => {
        const url = URL.createObjectURL(event.data);
        const oldUrl = img.src;
        img.src = url;

        if (oldUrl.startsWith('blob:')) {
            URL.revokeObjectURL(oldUrl);
        }
    };
}

async function startWebRTC() {
    stopCurrentStream();
    streamTitle.textContent = "WebRTC Stream";
    navWebrtc.classList.add('active');
    video.classList.remove('hidden');

    const pc = new RTCPeerConnection();
    currentPc = pc;

    pc.ontrack = (event) => {
        video.srcObject = event.streams[0] ?? new MediaStream([event.track]);
        video.play().catch(e => console.error("Error playing video:", e));
    };

    pc.addTransceiver('video', { direction: 'recvonly' });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const response = await fetch('/offer', {
        method: 'POST',
        body: JSON.stringify({
            sdp: pc.localDescription.sdp,
            type: pc.localDescription.type
        }),
        headers: { 'Content-Type': 'application/json' }
    });

    const answer = await response.json();
    await pc.setRemoteDescription(new RTCSessionDescription(answer));
}

// Initial Navigation
if (path === "/websocket") {
    startWebsocket();
} else if (path === "/webrtc") {
    startWebRTC();
} else {
    startMjpeg();
}
