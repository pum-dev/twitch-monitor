import os
import sys
import json
import asyncio
import threading
import logging
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT_DIR, "phase2"))
sys.path.insert(0, os.path.join(ROOT_DIR, "phase1"))

from stream_monitor import StreamMonitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static", static_url_path="/static")
monitor = None

def load_monitor():
    global monitor
    load_dotenv(os.path.join(ROOT_DIR, ".env"))
    client_id = os.getenv("TWITCH_CLIENT_ID")
    client_secret = os.getenv("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Define TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET en .env")
    monitor = StreamMonitor(client_id, client_secret)

def start_monitor_thread():
    """Ejecuta el monitor en un thread separado."""
    thread = threading.Thread(target=run_monitor, daemon=True)
    thread.start()

def run_monitor():
    """Ejecuta el loop del monitor."""
    asyncio.run(monitor.monitor_loop(interval=10))

@app.route("/")
def index():
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    return send_from_directory(static_dir, "index.html")

@app.route("/api/channels", methods=["GET"])
def get_channels():
    """Retorna lista de canales con estado actual."""
    channels_data = []
    for channel in monitor.channels:
        state = monitor.stream_states.get(channel, {})
        metrics = state.get("metrics", {})
        channels_data.append({
            "name": channel,
            "status": "ONLINE" if channel in monitor.analyzers else "OFFLINE",
            "bitrate": metrics.get("bitrate_kbps", None),
            "fps": metrics.get("fps", None),
            "av_sync": metrics.get("av_sync_offset", None),
            "last_update": state.get("timestamp", None)
        })
    return jsonify(channels_data)

@app.route("/api/events", methods=["GET"])
def get_events():
    """Retorna últimos eventos."""
    events_file = os.path.join(ROOT_DIR, "logs", "stream_events.json")
    if not os.path.exists(events_file):
        return jsonify([])
    
    try:
        with open(events_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        events = [json.loads(line.strip()) for line in lines[-20:] if line.strip()]
        return jsonify(events)
    except Exception as e:
        logger.error(f"Error reading events: {e}")
        return jsonify([])

@app.route("/api/channels/<channel>", methods=["DELETE"])
def remove_channel(channel):
    """Remueve un canal de la monitorización."""
    if channel in monitor.channels:
        monitor.channels.remove(channel)
        if channel in monitor.analyzers:
            monitor.stop_stream_analysis(channel)
        if channel in monitor.stream_states:
            del monitor.stream_states[channel]
        logger.info(f"Canal removido: {channel}")
        return jsonify({"status": "ok", "message": f"Canal {channel} removido"})
    return jsonify({"status": "error", "message": f"Canal {channel} no encontrado"}), 404

@app.route("/api/channels", methods=["POST"])
def add_channel():
    """Agrega un nuevo canal a la monitorización."""
    data = request.json
    channel = data.get("name", "").strip().lower()
    
    if not channel:
        return jsonify({"status": "error", "message": "Nombre de canal requerido"}), 400
    
    if channel in monitor.channels:
        return jsonify({"status": "error", "message": f"Canal {channel} ya está siendo monitoreado"}), 409
    
    monitor.channels.append(channel)
    logger.info(f"Canal agregado: {channel}")
    return jsonify({"status": "ok", "message": f"Canal {channel} agregado"}), 201

@app.route("/api/status", methods=["GET"])
def get_status():
    """Retorna estado general del monitor."""
    return jsonify({
        "total_channels": len(monitor.channels),
        "analyzing": len(monitor.analyzers),
        "logs_path": os.path.join(ROOT_DIR, "logs")
    })

if __name__ == "__main__":
    load_monitor()
    start_monitor_thread()
    app.run(host="0.0.0.0", port=5000, debug=False)