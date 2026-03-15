const img = document.getElementById('stream');
const streamTitle = document.getElementById('stream-title');
const navMjpeg = document.getElementById('nav-mjpeg');
const navWebsocket = document.getElementById('nav-websocket');

const path = window.location.pathname;
let currentWs = null;

function stopCurrentStream() {
    // Stop MJPEG
    img.src = "";

    // Stop WebSocket
    if (currentWs) {
        currentWs.close();
        currentWs = null;
    }
}

function startMjpeg() {
    streamTitle.textContent = "MJPEG Stream";
    navMjpeg.classList.add('active');
    // Using the new endpoint /mjpeg_stream
    img.src = "/mjpeg_stream";
}

function startWebsocket() {
    streamTitle.textContent = "WebSocket Stream";
    navWebsocket.classList.add('active');

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

    ws.onclose = () => {
        console.log("WebSocket connection closed.");
    };

    ws.onerror = (error) => {
        console.error("WebSocket error:", error);
    };
}

stopCurrentStream();

if (path === "/websocket") {
    startWebsocket();
} else {
    startMjpeg();
}