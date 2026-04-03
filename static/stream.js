const img = document.getElementById('stream');
const video = document.getElementById('web-video');
const streamTitle = document.getElementById('stream-title');
const navMjpeg = document.getElementById('nav-mjpeg');
const navWebsocket = document.getElementById('nav-websocket');
const navWebrtc = document.getElementById('nav-webrtc');

const pathParts = window.location.pathname.split('/').filter(p => p);
const protocol = pathParts.length > 0 ? pathParts[0] : 'mjpeg';
const streamId = pathParts.length > 1 ? pathParts[1] : 'stream_1';

document.getElementById('nav-mjpeg').href = `/mjpeg/${streamId}`;
document.getElementById('nav-websocket').href = `/websocket/${streamId}`;
document.getElementById('nav-webrtc').href = `/webrtc/${streamId}`;

let currentWs = null;
let currentPc = null;
let currentStatsInterval = null;

function stopCurrentStream() {
    // Stop MJPEG
    img.src = "";
    img.classList.add('hidden');

    // Stop WebRTC video
    video.srcObject = null;
    video.classList.add('hidden');
    
    // Clear stats
    document.getElementById('stat-fps').textContent = "0";
    document.getElementById('stat-latency').textContent = "0";
    document.getElementById('stat-bandwidth').textContent = "0";

    // Stop WebSocket
    if (currentWs) {
        currentWs.close();
        currentWs = null;
    }

    // Stop WebRTC PeerConnection
    if (currentStatsInterval) {
        clearInterval(currentStatsInterval);
        currentStatsInterval = null;
    }

    if (currentPc) {
        currentPc.close();
        currentPc = null;
    }

    // Clear active states
    [navMjpeg, navWebsocket, navWebrtc].forEach(btn => btn.classList.remove('active'));
}

let lastFrameTime = Date.now();
let framesReceived = 0;
let bytesReceived = 0;
let lastStatsUpdate = Date.now();

// Smoothing variables
let smoothedLatency = 0;
let smoothedFPS = 0;
const SMOOTHING_FACTOR = 0.1; // Lower = smoother but slower to adapt

function updateClientStats(latencyMs, bytes) {
    framesReceived++;
    bytesReceived += bytes;
    
    const now = Date.now();
    
    // Latency smoothing (Exponential Moving Average)
    if (latencyMs !== undefined) {
        // Handle negative values due to clock drift by taking absolute or clamping
        // On localhost, if we get negative, it means clocks are extremely close but offset.
        const validLatency = Math.max(0, latencyMs);
        if (smoothedLatency === 0) smoothedLatency = validLatency;
        else smoothedLatency = (validLatency * SMOOTHING_FACTOR) + (smoothedLatency * (1 - SMOOTHING_FACTOR));
        
        document.getElementById('stat-latency').textContent = Math.round(smoothedLatency);
    }

    if (now - lastStatsUpdate > 1000) {
        const rawFps = framesReceived / ((now - lastStatsUpdate) / 1000);
        const mbps = ((bytesReceived * 8) / (1024 * 1024 * ((now - lastStatsUpdate) / 1000))).toFixed(2);
        
        if (smoothedFPS === 0) smoothedFPS = rawFps;
        else smoothedFPS = (rawFps * 0.5) + (smoothedFPS * 0.5); // Faster FPS smoothing

        document.getElementById('stat-fps').textContent = smoothedFPS.toFixed(1);
        document.getElementById('stat-bandwidth').textContent = mbps;
        
        framesReceived = 0;
        bytesReceived = 0;
        lastStatsUpdate = now;
    }
}

function startMjpeg() {
    stopCurrentStream();
    streamTitle.textContent = "MJPEG Stream";
    navMjpeg.classList.add('active');
    img.classList.remove('hidden');
    img.src = `/mjpeg_stream/${streamId}`;
    
    img.onload = () => {
        updateClientStats(undefined, 0); // We don't know bytes easily, but we count the frame
    };
}

function startWebsocket() {
    stopCurrentStream();
    streamTitle.textContent = "WebSocket Stream";
    navWebsocket.classList.add('active');
    img.classList.remove('hidden');

    const ws = new WebSocket(`ws://${location.host}/ws/${streamId}`);
    ws.binaryType = 'blob';
    currentWs = ws;

    ws.onmessage = async (event) => {
        const data = await event.data.arrayBuffer();
        
        // First 8 bytes is the 64-bit float latency calculated by the server
        const view = new DataView(data);
        const serverLatencyMs = view.getFloat64(0, false); // big-endian
        
        const imageBlob = event.data.slice(8);
        const url = URL.createObjectURL(imageBlob);
        const oldUrl = img.src;
        img.src = url;

        if (oldUrl.startsWith('blob:')) {
            URL.revokeObjectURL(oldUrl);
        }
        
        updateClientStats(serverLatencyMs, data.byteLength);
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

    // Poll stats for WebRTC
    let lastWebRTCStats = null;
    currentStatsInterval = setInterval(async () => {
        if (!currentPc) return;
        const stats = await currentPc.getStats();
        stats.forEach(report => {
            if (report.type === 'inbound-rtp' && report.kind === 'video') {
                const now = Date.now();
                if (lastWebRTCStats) {
                    const dt = (now - lastWebRTCStats.time) / 1000;
                    const db = report.bytesReceived - lastWebRTCStats.bytes;
                    const mbps = ((db * 8) / (1024 * 1024 * dt)).toFixed(2);
                    document.getElementById('stat-bandwidth').textContent = mbps;

                    const df = report.framesDecoded - lastWebRTCStats.frames;
                    const fps = (df / dt).toFixed(1);
                    document.getElementById('stat-fps').textContent = fps;
                }
                lastWebRTCStats = { time: now, bytes: report.bytesReceived, frames: report.framesDecoded };
            }
        });
    }, 1000);

    pc.addTransceiver('video', { direction: 'recvonly' });

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const response = await fetch(`/offer/${streamId}`, {
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
if (protocol === "websocket") {
    startWebsocket();
} else if (protocol === "webrtc") {
    startWebRTC();
} else {
    startMjpeg();
}

// Stats Polling for Server Resources
setInterval(async () => {
    try {
        const response = await fetch('/stats');
        const stats = await response.json();
        
        document.getElementById('stat-cpu').textContent = stats.cpu.toFixed(1);
        document.getElementById('stat-ram').textContent = stats.ram.toFixed(0);
        
        const isMjpeg = protocol === "mjpeg" || protocol === "";
        const isWebRTC = protocol === "webrtc";

        if (isMjpeg) {
             document.getElementById('stat-bandwidth').textContent = stats.total_bandwidth_mbps.toFixed(2);
             document.getElementById('stat-fps').textContent = stats.fps.toFixed(1);
             document.getElementById('stat-latency').textContent = stats.latency.toFixed(0);
        } else if (isWebRTC) {
             document.getElementById('stat-latency').textContent = stats.latency.toFixed(0);
             // Bandwidth is already being updated by the RTCPeerConnection stats interval
        }
    } catch (e) {
        console.error("Error fetching stats:", e);
    }
}, 2000);
