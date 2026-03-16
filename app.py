# ============================================================
#  SolarClean — Render Cloud Streaming Server
#  Purpose : Relay JPEG frames from ESP32-CAM to Flutter app
#  Deploy  : Render.com (free tier, persistent service)
#  Author  : Production Build
#  Version : 2.0
#
#  Endpoints:
#    GET  /                → Health check
#    GET  /stream_status   → Is streaming active? (polled by ESP32-CAM)
#    POST /start_stream    → Activate streaming   (called by Flutter app)
#    POST /stop_stream     → Deactivate streaming (called by Flutter app)
#    POST /upload_frame    → ESP32-CAM pushes JPEG frame here
#    GET  /live_frame      → App polls latest JPEG frame (snapshot)
#    GET  /video_feed      → MJPEG multipart stream (browser/debug use)
# ============================================================

from flask import Flask, request, jsonify, send_file, Response
from io import BytesIO
import time
import os
import threading
import logging

# ─── Logging Setup ──────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s — %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

app = Flask(__name__)

# ─── Global State ────────────────────────────────────────────
streaming_active  = True          # Streaming is ON by default at server start
latest_frame      = None          # Raw bytes of the latest JPEG frame
frame_timestamp   = 0.0           # Unix timestamp of last received frame
frame_count       = 0             # Total frames received since server start
frame_lock        = threading.Lock()  # Thread-safe frame access

# ─── Constants ───────────────────────────────────────────────
MJPEG_BOUNDARY    = b'--frame'
FRAME_STALE_SEC   = 10            # Frame older than this is considered stale


# ============================================================
#  HEALTH CHECK
# ============================================================
@app.route("/")
def home():
    uptime = time.time() - server_start_time
    return jsonify({
        "service"         : "SolarClean Streaming Server",
        "version"         : "2.0",
        "status"          : "online",
        "streaming_active": streaming_active,
        "frames_received" : frame_count,
        "uptime_seconds"  : round(uptime, 1),
        "frame_age_sec"   : round(time.time() - frame_timestamp, 1)
                            if frame_timestamp > 0 else None
    })


# ============================================================
#  STREAM CONTROL  (Flutter App → Server)
# ============================================================
@app.route("/start_stream", methods=["GET", "POST"])
def start_stream():
    global streaming_active
    streaming_active = True
    log.info("Streaming STARTED by app.")
    return jsonify({"status": "ok", "streaming": True})


@app.route("/stop_stream", methods=["GET", "POST"])
def stop_stream():
    global streaming_active
    streaming_active = False
    log.info("Streaming STOPPED by app.")
    return jsonify({"status": "ok", "streaming": False})


@app.route("/stream_status", methods=["GET"])
def stream_status():
    """
    Polled by ESP32-CAM every 2 seconds.
    Returns whether the server wants frames uploaded.
    """
    return jsonify({"streaming": streaming_active})


# ============================================================
#  FRAME UPLOAD  (ESP32-CAM → Server)
# ============================================================
@app.route("/upload_frame", methods=["POST"])
def upload_frame():
    """
    ESP32-CAM POSTs raw JPEG bytes here.
    Only stored if streaming is active.
    """
    global latest_frame, frame_timestamp, frame_count

    if not streaming_active:
        return jsonify({"status": "ignored", "reason": "streaming_inactive"})

    data = request.data
    if not data:
        return jsonify({"status": "error", "reason": "empty_payload"}), 400

    with frame_lock:
        latest_frame    = data
        frame_timestamp = time.time()
        frame_count    += 1

    return jsonify({"status": "ok", "frame": frame_count})


# ============================================================
#  FRAME DELIVERY  (Server → Flutter App)
# ============================================================
@app.route("/live_frame", methods=["GET"])
def live_frame():
    """
    Flutter app polls this endpoint to get the latest JPEG.
    Returns 404 if no frame has been received yet,
    or 503 if the last frame is too stale.
    """
    with frame_lock:
        frame = latest_frame
        ts    = frame_timestamp

    if frame is None:
        return jsonify({
            "error": "no_frame",
            "message": "No frame received from ESP32-CAM yet."
        }), 404

    age = time.time() - ts
    if age > FRAME_STALE_SEC:
        return jsonify({
            "error"  : "stale_frame",
            "message": f"Last frame is {age:.0f}s old. ESP32-CAM may be offline.",
            "age_sec": round(age, 1)
        }), 503

    return send_file(
        BytesIO(frame),
        mimetype="image/jpeg",
        max_age=0  # Prevent any caching — always serve fresh frame
    )


# ============================================================
#  MJPEG STREAM  (Server → Browser / Debug)
#  Used for browser-based /live page and optional webview use.
# ============================================================
@app.route("/video_feed")
def video_feed():
    """
    Continuous MJPEG multipart stream.
    Targets ~20 FPS (50ms sleep between frames).
    """
    def generate():
        last_frame_sent = None
        while True:
            with frame_lock:
                frame = latest_frame

            # Only yield if we have a new frame
            if frame is not None and frame is not last_frame_sent:
                last_frame_sent = frame
                yield (
                    MJPEG_BOUNDARY +
                    b'\r\nContent-Type: image/jpeg\r\n\r\n' +
                    frame +
                    b'\r\n'
                )

            time.sleep(0.05)  # 20 FPS cap

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control"  : "no-cache, no-store, must-revalidate",
            "Pragma"         : "no-cache",
            "Expires"        : "0",
            "X-Accel-Buffering": "no"   # Important for Nginx-proxied Render
        }
    )


@app.route("/live")
def live_view():
    """Simple HTML page for browser-based monitoring."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SolarClean — Live Feed</title>
        <style>
            body { background: #0d1117; color: #fff;
                   font-family: sans-serif; text-align: center; padding: 40px; }
            h2   { color: #1a73e8; }
            img  { border: 2px solid #30363d; border-radius: 12px; max-width: 100%; }
            .badge { display: inline-block; background: #ea4335;
                     padding: 4px 12px; border-radius: 20px;
                     font-size: 12px; font-weight: bold;
                     margin-bottom: 16px; letter-spacing: 1px; }
        </style>
    </head>
    <body>
        <h2>SolarClean Live Stream</h2>
        <div class="badge">&#9679; LIVE</div><br>
        <img src="/video_feed" width="640" alt="Live Feed">
        <p style="color:#8b949e; font-size:13px; margin-top:16px;">
            ESP32-CAM via Render Cloud Relay
        </p>
    </body>
    </html>
    """


# ============================================================
#  SERVER ENTRY POINT
# ============================================================
server_start_time = time.time()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    log.info(f"SolarClean Streaming Server starting on port {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
