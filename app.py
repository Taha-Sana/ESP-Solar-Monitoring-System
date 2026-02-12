from flask import Flask, request, jsonify, Response
import requests
import os  # <--- Add this for environment variables

app = Flask(__name__)

# Store sensor data and servo state
sensor_data = {"temperature": None, "humidity": None}
servo_state = {"angle": 0}

# ESP32-CAM URL (to be set dynamically)
esp_cam_url = None

# Endpoint for ESP32-CAM to register its stream URL
@app.route("/register_stream", methods=["POST"])
def register_stream():
    global esp_cam_url
    data = request.get_json()
    esp_cam_url = data.get("stream_url")
    return jsonify({"status": "registered"})

# Endpoint for Flutter app to get the stream URL
@app.route("/stream-url", methods=["GET"])
def stream_url():
    if not esp_cam_url:
        return jsonify({"error": "Stream not registered"}), 400
    return jsonify({"stream_url": esp_cam_url})

# ESP32 sends sensor data
@app.route("/send_sensor", methods=["POST"])
def receive_sensor():
    global sensor_data
    data = request.get_json()
    sensor_data.update(data)
    return jsonify({"status": "ok"})

# Flutter app fetch sensor data
@app.route("/get_sensor", methods=["GET"])
def get_sensor():
    return jsonify(sensor_data)

# Flutter app controls servo
@app.route("/servo", methods=["POST"])
def control_servo():
    global servo_state
    data = request.get_json()
    servo_state["angle"] = data.get("angle", servo_state["angle"])
    # ESP32 polling will fetch this value
    return jsonify({"status": "ok"})

# ESP32 polling endpoint
@app.route("/get_servo_state", methods=["GET"])
def get_servo_state():
    return jsonify(servo_state)

# ================= RUN SERVER =================
if __name__ == "__main__":
    # Use the PORT environment variable if provided (Render sets this automatically)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
