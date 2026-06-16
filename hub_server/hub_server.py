"""
OmniBand Hub Server
====================
Corre no Raspberry Pi (ou qualquer máquina na rede).
Recebe eventos POST do wearable (OmniBand) e serve a API REST
para a App Móvel (Dashboard).

Endpoints:
  POST /api/event     - Wearable envia comando (ligar/desligar/dim/toggle)
  GET  /api/devices   - App lê estado de todos os dispositivos
  POST /api/control   - App envia comando manual
  GET  /api/status    - Estado do wearable (battery, rssi, etc.)

A App Móvel (Dashboard) é servida na raiz (/) e pode ser acedida
em http://<ip-do-rpi>:8080
"""

import json
import os
import time
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Import plug controller (Tapo P110 support)
from plug_controller import set_plug_state, get_plug_state, sync_all_plugs

# Import Firebase sync
from firebase_sync import sync_all as firebase_sync_all

HOST = "0.0.0.0"
PORT = 8080

# Path to the app_mobile directory (relative to this script)
APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app_mobile")

DEVICES = {
    "corredor": {"light": False, "brightness": 100},
    "sala": {"light": False, "brightness": 100},
    "quarto": {"light": False, "brightness": 100},
}

WEARABLE_STATUS = {
    "connected": False,
    "last_seen": 0,
    "battery": 0,
    "rssi": 0,
    "active_room": "corredor",
}

HISTORY = []


def apply_action(room, action):
    if room not in DEVICES:
        return {"error": f"Room '{room}' not found"}
    device = DEVICES[room]

    # Determinar novo estado pretendido
    new_state = device["light"]
    if action == "on":
        new_state = True
    elif action == "off":
        new_state = False
    elif action == "toggle":
        new_state = not device["light"]
    elif action == "dim_up":
        device["brightness"] = min(100, device["brightness"] + 10)
    elif action == "dim_down":
        device["brightness"] = max(0, device["brightness"] - 10)
    elif action == "set_brightness":
        pass  # Requires value param
    else:
        return {"error": f"Unknown action '{action}'"}

    # Se o estado mudou (on/off/toggle) e há tomada física, liga/desliga
    if action in ("on", "off", "toggle"):
        device["light"] = new_state
        plug_success, plug_state = set_plug_state(room, new_state)
        # Se a tomada respondeu, usa o estado real dela
        if plug_success:
            device["light"] = plug_state if isinstance(plug_state, bool) else new_state

    return {"room": room, **device}


class OmniBandHandler(BaseHTTPRequestHandler):

    def _set_headers(self, code=200, content_type="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _reply_json(self, data, code=200):
        self._set_headers(code)
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def _serve_static(self, filepath):
        """Serve a static file from the app_mobile directory."""
        # Security: ensure filepath is within APP_DIR
        abs_path = os.path.normpath(os.path.join(APP_DIR, filepath))
        if not abs_path.startswith(os.path.normpath(APP_DIR)):
            self._reply_json({"error": "Forbidden"}, 403)
            return

        if not os.path.isfile(abs_path):
            self._reply_json({"error": "Not found"}, 404)
            return

        content_type, _ = mimetypes.guess_type(abs_path)
        if content_type is None:
            content_type = "application/octet-stream"

        try:
            with open(abs_path, "rb") as f:
                data = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(data)
        except IOError:
            self._reply_json({"error": "Could not read file"}, 500)

    def do_OPTIONS(self):
        self._set_headers(204)

    # ───────────────────────────────
    #  POST endpoints
    # ───────────────────────────────
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # ---- POST /api/event ----
        if path == "/api/event":
            body = self._read_body()

            device_id = body.get("device_id", "unknown")
            room = body.get("room", "corredor")
            action = body.get("action", "toggle")
            battery = body.get("battery", 0)
            rssi = body.get("rssi", 0)
            metrics = body.get("metrics", {})

            # Update wearable status
            WEARABLE_STATUS["connected"] = True
            WEARABLE_STATUS["last_seen"] = time.time()
            WEARABLE_STATUS["battery"] = battery
            WEARABLE_STATUS["rssi"] = rssi
            WEARABLE_STATUS["active_room"] = room

            # Apply action
            result = apply_action(room, action)

            # Log to history
            entry = {
                "timestamp": time.strftime("%H:%M:%S"),
                "source": device_id,
                "room": room,
                "action": action,
                "result": result,
                "metrics": metrics,
            }
            HISTORY.append(entry)
            if len(HISTORY) > 100:
                HISTORY.pop(0)

            # Sync to Firebase after every event
            firebase_sync_all(DEVICES, WEARABLE_STATUS, HISTORY)

            has_error = "error" in result
            code = 200 if not has_error else 400
            self._reply_json(
                {
                    "status": "error" if has_error else "ok",
                    "message": result.get("error", f"{action} applied to {room}"),
                    "device_state": result,
                    "wearable": {
                        "battery": battery,
                        "rssi": rssi,
                    },
                },
                code,
            )
            return

        # ---- POST /api/control ----
        if path == "/api/control":
            body = self._read_body()
            room = body.get("room", "corredor")
            action = body.get("action", "toggle")
            brightness = body.get("brightness")

            if action == "set_brightness" and brightness is not None:
                if room in DEVICES:
                    DEVICES[room]["brightness"] = max(0, min(100, brightness))
                    result = DEVICES[room]
                else:
                    result = {"error": f"Room '{room}' not found"}
            else:
                result = apply_action(room, action)

            # Sync to Firebase after manual control
            firebase_sync_all(DEVICES, WEARABLE_STATUS, HISTORY)

            has_error = "error" in result
            self._reply_json(
                {
                    "status": "error" if has_error else "ok",
                    "device_state": result,
                },
                200 if not has_error else 400,
            )
            return

        self._reply_json({"error": "Not found"}, 404)

    # ───────────────────────────────
    #  GET endpoints
    # ───────────────────────────────
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # API endpoints
        if path == "/api/devices":
            self._reply_json(
                {
                    "rooms": DEVICES,
                    "count": len(DEVICES),
                }
            )
            return

        if path == "/api/status":
            is_online = (time.time() - WEARABLE_STATUS["last_seen"]) < 30
            self._reply_json(
                {
                    "wearable": {
                        **WEARABLE_STATUS,
                        "online": is_online,
                        "last_seen_ago": (
                            int(time.time() - WEARABLE_STATUS["last_seen"])
                            if WEARABLE_STATUS["last_seen"]
                            else None
                        ),
                    },
                    "history": list(reversed(HISTORY[-20:])),
                }
            )
            return

        if path == "/api/history":
            self._reply_json({"history": list(reversed(HISTORY))})
            return

        # ── Serve static files (Dashboard App) ──
        # Root path -> index.html
        if path == "" or path == "/":
            self._serve_static("index.html")
            return

        # Any other path -> try as static file
        # Remove leading slash
        filepath = path.lstrip("/")
        self._serve_static(filepath)

    def log_message(self, format, *args):
        print(f"[hub] {args[0]} {args[1]} {args[2]}")


def main():
    # Verify app directory exists
    print(f"  App directory: {APP_DIR}")
    print(f"  index.html exists: {os.path.isfile(os.path.join(APP_DIR, 'index.html'))}")

    server = HTTPServer((HOST, PORT), OmniBandHandler)
    print()
    print("═" * 60)
    print("  OmniBand Hub Server")
    print("═" * 60)
    print(f"  Endereço:        http://{HOST}:{PORT}")
    print(f"  Dashboard App:   http://<ip-do-rpi>:{PORT}")
    print(f"  ── API Endpoints ──")
    print(f"  POST /api/event    ←  Wearable (OmniBand) envia comandos")
    print(f"  GET  /api/devices  →  App Móvel (estado das divisões)")
    print(f"  POST /api/control  ←  App Móvel (comandos manuais)")
    print(f"  GET  /api/status   →  Estado do wearable + histórico")
    print("═" * 60)
    print("  Ctrl+C para parar")
    print("═" * 60)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[hub] Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()