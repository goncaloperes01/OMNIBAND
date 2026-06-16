"""
OmniBand - Plug Controller
============================
Controla smart plugs/lâmpadas via rede local.
Suporta: Tapo P110 (via python-kasa)

Fallback automático para simulação se a tomada estiver offline.
"""

import json
import os
import asyncio
import threading
import time

# Path to config file
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugs_config.json")

# Virtual state cache (used when real plug is offline)
_virtual_state = {}

# Real plug state cache (last known from actual device)
_real_state = {}

# Carregar configuração das tomadas
def load_config():
    if not os.path.isfile(CONFIG_PATH):
        return {"plugs": {}, "tp_link_credentials": {"email": "", "password": ""}}

    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def is_plug_configured(room):
    """Verifica se uma divisão tem tomada real configurada."""
    config = load_config()
    return room in config.get("plugs", {})


def get_plug_info(room):
    """Devolve info da tomada para uma divisão, ou None."""
    config = load_config()
    return config.get("plugs", {}).get(room, None)


# ─── Controlo real via python-kasa (assíncrono) ──────────
async def _kasa_set_state(host, email, password, turn_on):
    """Liga/desliga uma Tapo P110 via protocolo local."""
    try:
        from kasa import SmartDevice

        dev = SmartDevice(host)
        dev.credentials = (email, password)
        await dev.update()

        current = dev.is_on
        if turn_on and not current:
            await dev.turn_on()
            await dev.update()
            return True, dev.is_on
        elif not turn_on and current:
            await dev.turn_off()
            await dev.update()
            return True, dev.is_on
        else:
            return True, dev.is_on  # Já estava no estado desejado

    except ImportError:
        return False, None
    except Exception as e:
        print(f"[plug] Erro kasa ({host}): {e}")
        return False, None


async def _kasa_get_state(host, email, password):
    """Lê o estado atual de uma Tapo P110."""
    try:
        from kasa import SmartDevice

        dev = SmartDevice(host)
        dev.credentials = (email, password)
        await dev.update()
        return True, dev.is_on
    except Exception as e:
        print(f"[plug] Erro kasa get_state ({host}): {e}")
        return False, None


def _run_async(coro):
    """Executa uma coroutine async de forma síncrona (bloqueante)."""
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(coro)
        loop.close()
        return result
    except Exception as e:
        print(f"[plug] Erro async: {e}")
        return False, None


# ─── API pública ─────────────────────────────────────────
def set_plug_state(room, turn_on):
    """
    Liga/desliga a tomada de uma divisão.
    Retorna: (sucesso, estado_real, estado_final)
      - estado_real: True se conseguiu contactar a tomada
      - estado_final: True se ligada, False se desligada
    """
    plug = get_plug_info(room)
    if not plug:
        # Sem tomada configurada → simulação
        _virtual_state[room] = turn_on
        return True, turn_on

    host = plug["ip"]
    config = load_config()
    creds = config.get("tp_link_credentials", {})
    email = creds.get("email", "")
    password = creds.get("password", "")

    if not email or not password or email == "PREENCHE_AQUI_O_TEU_EMAIL_TP_LINK":
        print(f"[plug] Credenciais TP-Link não configuradas. A usar simulação para '{room}'.")
        _virtual_state[room] = turn_on
        return True, turn_on

    success, state = _run_async(_kasa_set_state(host, email, password, turn_on))

    if success:
        _real_state[room] = state
        print(f"[plug] Tomada '{room}' -> {'LIGADA' if state else 'DESLIGADA'} (real)")
        return True, state
    else:
        print(f"[plug] Falha ao contactar tomada '{room}'. A usar simulação.")
        _virtual_state[room] = turn_on
        return False, turn_on


def get_plug_state(room):
    """
    Lê o estado atual de uma tomada.
    Retorna: (bool ligada, bool is_real)
    """
    plug = get_plug_info(room)
    if not plug:
        # Apenas simulação
        return _virtual_state.get(room, False), False

    # Se temos estado real em cache, usa
    if room in _real_state:
        return _real_state[room], True

    # Tenta ler da tomada
    host = plug["ip"]
    config = load_config()
    creds = config.get("tp_link_credentials", {})
    email = creds.get("email", "")
    password = creds.get("password", "")

    if not email or not password or email == "PREENCHE_AQUI_O_TEU_EMAIL_TP_LINK":
        return _virtual_state.get(room, False), False

    success, state = _run_async(_kasa_get_state(host, email, password))

    if success:
        _real_state[room] = state
        return state, True
    else:
        return _virtual_state.get(room, False), False


def sync_all_plugs(devices_dict):
    """
    Sincroniza o estado real das tomadas para o dicionário de dispositivos.
    Deve ser chamado periodicamente ou após cada comando.
    """
    for room in list(devices_dict.keys()):
        plug = get_plug_info(room)
        if plug:
            state, is_real = get_plug_state(room)
            if is_real and room in devices_dict:
                devices_dict[room]["light"] = state


# ─── Diagnóstico via linha de comandos ───────────────────
def discover():
    """Tenta descobrir tomadas na rede."""
    print("[plug] A descobrir dispositivos Tapo na rede...")
    try:
        result = _run_async(_discover_async())
        return result
    except Exception as e:
        print(f"[plug] Erro no discover: {e}")
        return []


async def _discover_async():
    from kasa import Discover
    devices = await Discover.discover()
    discovered = []
    for ip, dev in devices.items():
        await dev.update()
        info = {
            "ip": ip,
            "model": dev.model if hasattr(dev, 'model') else "unknown",
            "name": dev.alias if hasattr(dev, 'alias') else "unknown",
            "is_on": dev.is_on if hasattr(dev, 'is_on') else None,
        }
        discovered.append(info)
        print(f"  Encontrado: {dev.alias} ({ip}) - {'LIGADO' if dev.is_on else 'DESLIGADO'}")
    return discovered


if __name__ == "__main__":
    # Teste rápido
    print("=" * 50)
    print("OmniBand Plug Controller - Diagnóstico")
    print("=" * 50)

    config = load_config()
    print(f"\nConfig: {len(config.get('plugs', {}))} tomada(s) configurada(s)")
    for room, info in config.get("plugs", {}).items():
        print(f"  {room}: {info['name']} @ {info['ip']}")

    # Discover
    print("\nA procurar dispositivos na rede...")
    devices = discover()
    if devices:
        print(f"\nEncontrados {len(devices)} dispositivo(s):")
        for d in devices:
            print(f"  {d['name']} @ {d['ip']} ({d['model']}) - {'ON' if d['is_on'] else 'OFF'}")
    else:
        print("Nenhum dispositivo encontrado. Verifica se:")
        print("  - A tomada está ligada e na mesma rede")
        print("  - As credenciais estão corretas em plugs_config.json")
        print("  - O IP está correto")