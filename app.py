from flask import Flask, request, jsonify, send_file
from io import BytesIO
import os

app = Flask(__name__)

# ================= GLOBAL STATES =================
streaming_active = False
latest_frame = None
sensor_data = {"temperature": 0, "voltage": 0}
servo_angle = 0   # +60 or -60


# ================= STREAM CONTROL =================
@app.route("/start_stream", methods=["POST"])
def start_stream():
    global streaming_active
    streaming_active = True
    return jsonify({"status": "stream_started"})


@app.route("/stop_stream", methods=["POST"])
def stop_stream():
    global streaming_active
    streaming_active = False
    return jsonify({"status": "stream_stopped"})


@app.route("/stream_status", methods=["GET"])
def stream_status():
    return jsonify({"streaming": streaming_active})


@app.route("/upload_frame", methods=["POST"])
def upload_frame():
    global latest_frame
    if streaming_active:
        latest_frame = request.data
    return "ok"


@app.route("/live_frame", methods=["GET"])
def live_frame():
    if latest_frame is None:
        return "No frame", 404
    return send_file(BytesIO(latest_frame), mimetype='image/jpeg')


# ================= SENSOR =================
@app.route("/send_sensor", methods=["POST"])
def receive_sensor():
    global sensor_data
    sensor_data = request.json
    return jsonify({"status": "received"})


@app.route("/get_sensor", methods=["GET"])
def get_sensor():
    return jsonify(sensor_data)


# ================= SERVO =================
@app.route("/set_servo", methods=["POST"])
def set_servo():
    global servo_angle
    data = request.json
    angle = data.get("angle", 0)

    if angle == 60 or angle == -60:
        servo_angle = angle
        return jsonify({"status": "updated"})
    else:
        return jsonify({"error": "Invalid angle"}), 400


@app.route("/get_servo", methods=["GET"])
def get_servo():
    return jsonify({"angle": servo_angle})


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
