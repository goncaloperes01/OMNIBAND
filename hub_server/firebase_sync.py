"""
OmniBand - Firebase Sync Module
=================================
Sincroniza o estado dos dispositivos, wearable e histórico
com o Firebase Realtime Database.

Requer:
  - pip install firebase-admin
  - serviceAccountKey.json na mesma pasta
"""

import json
import os
import time
from datetime import datetime

FIREBASE_URL = "https://omniband-p2-default-rtdb.firebaseio.com"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json")

# Firebase app instance (lazy initialized)
_db = None


def _init_firebase():
    """Inicializa Firebase Admin SDK (lazy)."""
    global _db
    if _db is not None:
        return True

    if not os.path.isfile(CONFIG_PATH):
        print("[firebase] serviceAccountKey.json não encontrado. Firebase desativado.")
        return False

    try:
        import firebase_admin
        from firebase_admin import credentials, db

        cred = credentials.Certificate(CONFIG_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_URL})
        _db = db
        print(f"[firebase] Firebase inicializado: {FIREBASE_URL}")
        return True

    except Exception as e:
        print(f"[firebase] Erro ao inicializar Firebase: {e}")
        return False


def _safe_set(ref_path, value):
    """Escreve valor no Firebase com segurança."""
    try:
        if _db is not None:
            ref = _db.reference(ref_path)
            ref.set(value)
            return True
    except Exception as e:
        print(f"[firebase] Erro ao escrever {ref_path}: {e}")
    return False


def sync_device_state(devices):
    """
    Sincroniza o estado das divisões para Firebase.
    Estrutura: /devices/{room}/  {light, brightness}
    """
    if not _init_firebase():
        return False

    print(f"[firebase] A sincronizar {len(devices)} divisões...")
    for room, state in devices.items():
        ref_path = f"/devices/{room}"
        _safe_set(ref_path, state)
    return True


def sync_wearable_status(wearable_status):
    """
    Sincroniza o estado do wearable para Firebase.
    Estrutura: /wearable/  {online, battery, rssi, active_room, last_seen}
    """
    if not _init_firebase():
        return False

    # Calcular online
    last_seen = wearable_status.get("last_seen", 0)
    is_online = (time.time() - last_seen) < 30

    data = {
        "online": is_online,
        "battery": wearable_status.get("battery", 0),
        "rssi": wearable_status.get("rssi", 0),
        "active_room": wearable_status.get("active_room", "corredor"),
        "last_seen": last_seen,
        "last_seen_ago": int(time.time() - last_seen) if last_seen else None,
        "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _safe_set("/wearable", data)
    return True


def sync_history(history):
    """
    Sincroniza o histórico de comandos para Firebase.
    Estrutura: /history/{index}/  {timestamp, room, action, source}
    Apenas os últimos 20 eventos.
    """
    if not _init_firebase():
        return False

    recent = list(reversed(history[-20:]))
    data = {}
    for i, entry in enumerate(recent):
        data[str(i)] = {
            "timestamp": entry.get("timestamp", ""),
            "source": entry.get("source", ""),
            "room": entry.get("room", ""),
            "action": entry.get("action", ""),
        }
    _safe_set("/history", data)
    return True


def sync_all(devices, wearable_status, history):
    """
    Sincroniza tudo (divisões + wearable + histórico) para Firebase.
    """
    sync_device_state(devices)
    sync_wearable_status(wearable_status)
    sync_history(history)


# ─── Teste rápido ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("OmniBand Firebase Sync - Teste")
    print("=" * 50)

    _init_firebase()

    # Dados de exemplo
    test_devices = {
        "corredor": {"light": False, "brightness": 100},
        "sala": {"light": True, "brightness": 75},
        "quarto": {"light": False, "brightness": 50},
    }
    test_wearable = {
        "connected": True,
        "last_seen": time.time(),
        "battery": 85,
        "rssi": -45,
        "active_room": "sala",
    }
    test_history = [
        {"timestamp": "14:30:00", "source": "omniband-coreink-01", "room": "sala", "action": "toggle"},
        {"timestamp": "14:29:00", "source": "mobile-app", "room": "corredor", "action": "on"},
    ]

    print("\nA escrever dados de teste no Firebase...")
    sync_all(test_devices, test_wearable, test_history)
    print("  ✅ Dados escritos!")

    print("\nA ler de volta do Firebase...")
    try:
        from firebase_admin import db
        ref = db.reference("/")
        result = ref.get()
        print("  Dados lidos:", json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"  Erro ao ler: {e}")