# Stream Comparison App

This is a FastAPI application designed to compare different video streaming protocols: MJPEG, WebSocket, and WebRTC. It ingests RTSP video streams configured from a YAML file and serves them through multiple endpoints to help visualize performance differences such as latency, bandwidth, and resource consumption.

### Key Architectural Features:
- **Multi-Protocol Support**: Compare MJPEG, WebSocket, and WebRTC streams side-by-side.
- **RTSP Ingestion**: Continuously captures frames from RTSP cameras using a threaded background reader, reducing latency.
- **Resource Monitoring**: Automatically tracks and outputs Process CPU + RAM statistics metrics to your console and exposes via a `/stats` endpoint.
- **Dynamic Configuration**: Easily add or configure camera streams using a `cameras.yaml` file without altering the source code.

## 1. Setup

First, make sure you have Python installed. It is highly recommended to use a virtual environment.

```bash
# Create a virtual environment (optional but recommended)
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

## 2. Install Dependencies

Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
pip install pyyaml # Required for parsing cameras.yaml
```

## 3. Configuration

Configure your RTSP streams by creating or editing the `cameras.yaml` file in the root directory. Example:

```yaml
cam_1: rtsp://localhost:8554/cam_1
cam_2: rtsp://localhost:8554/cam_2
```

## 4. Run the Server

You can run the server directly using Python. 

```bash
python main.py
```

By default, the server runs on `0.0.0.0:8000`. You can specify a custom host and port:
```bash
python main.py --host 127.0.0.1 --port 8080
```

## 5. View the Streams

Once the server is running, you can access the streams by opening your web browser:
- **MJPEG**: `http://localhost:8000/mjpeg/{stream_id}`
- **WebSocket**: `http://localhost:8000/websocket/{stream_id}`
- **WebRTC**: `http://localhost:8000/webrtc/{stream_id}`

For example, to view `stream_1` via WebRTC, go to:
`http://localhost:8000/webrtc/stream_1`

The root URL (`http://localhost:8000/`) will automatically redirect to the first MJPEG stream setup. System resource usage logs will populate in your terminal, and detailed stats are available at `/stats`.
