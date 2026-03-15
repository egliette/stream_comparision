const img = document.getElementById('stream');
const ws = new WebSocket(`ws://${location.host}/ws`);
ws.binaryType = 'blob';

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