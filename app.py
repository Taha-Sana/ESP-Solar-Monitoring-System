from flask import Flask, request, jsonify

app = Flask(__name__)

# ========================
# Global storage
# ========================
sensor_data = {"temperature": None, "humidity": None}
servo_state = {"angle": 0}
esp_cam_url = None  # Stream URL to be set by ESP32-CAM

# ========================
# Root route
# ========================
@app.route("/", methods=["GET"])
def home():
    return "ESP Solar Monitoring System Service is Live!"

# ========================
# ESP32-CAM stream routes
# ========================
# ESP32-CAM registers its stream URL
@app.route("/register_stream", methods=["POST"])
def register_stream():
    global esp_cam_url
    data = request.get_json()
    esp_cam_url = data.get("stream_url")
    return jsonify({"status": "registered"})

# Flutter app fetches stream URL
@app.route("/stream-url", methods=["GET"])
def stream_url():
    if not esp_cam_url:
        return jsonify({"error": "Stream not registered"}), 404
    return jsonify({"stream_url": esp_cam_url})

# Optional direct /stream route for testing
@app.route("/stream", methods=["GET"])
def stream_redirect():
    if esp_cam_url:
        return jsonify({"stream_url": esp_cam_url})
    else:
        return jsonify({"error": "No stream registered"}), 404

# ========================
# Sensor endpoints
# ========================
# ESP32 sends sensor data
@app.route("/send_sensor", methods=["POST"])
def receive_sensor():
    global sensor_data
    data = request.get_json()
    sensor_data.update(data)
    return jsonify({"status": "ok"})

# Flutter app fetches sensor data
@app.route("/get_sensor", methods=["GET"])
def get_sensor():
    return jsonify(sensor_data)

# ========================
# Servo endpoints
# ========================
# Flutter app controls servo
@app.route("/servo", methods=["POST"])
def control_servo():
    global servo_state
    data = request.get_json()
    servo_state["angle"] = data.get("angle", servo_state["angle"])
    # ESP32 can poll this value
    return jsonify({"status": "ok"})

# ESP32 polling endpoint
@app.route("/get_servo_state", methods=["GET"])
def get_servo_state():
    return jsonify(servo_state)

# ========================
# Run Flask
# ========================
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
