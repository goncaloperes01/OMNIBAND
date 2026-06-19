from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
import requests

app = Flask(__name__)

DB_NAME = "smarthome.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def log_event(event_type, source, gesture_name, device_name, action, previous_state, new_state):
    db = get_db()
    db.execute(
        '''
        INSERT INTO EventLogs
        (event_type, source, gesture_name, device_name, action, previous_state, new_state)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (event_type, source, gesture_name, device_name, action, previous_state, new_state)
    )
    db.commit()


def set_device_state(device_id, action, source="manual", gesture_name=None):
    db = get_db()

    device = db.execute(
        '''
        SELECT id, name, ip_address, current_state
        FROM Devices
        WHERE id = ?
        ''',
        (device_id,)
    ).fetchone()

    if not device:
        return {"sucesso": False, "erro": "Dispositivo não encontrado"}

    current_state = device["current_state"]

    if action == "toggle":
        new_state = "off" if current_state == "on" else "on"
    elif action in ["on", "off"]:
        new_state = action
    else:
        return {"sucesso": False, "erro": "Ação inválida"}

    shelly_url = f"http://{device['ip_address']}/relay/0?turn={new_state}"

    try:
        # Quando tiveres a Shelly real, descomenta:
        # response = requests.get(shelly_url, timeout=3)

        db.execute(
            'UPDATE Devices SET current_state = ? WHERE id = ?',
            (new_state, device_id)
        )
        db.commit()

        log_event(
            event_type="device_action",
            source=source,
            gesture_name=gesture_name,
            device_name=device["name"],
            action=action,
            previous_state=current_state,
            new_state=new_state
        )

        return {
            "sucesso": True,
            "device_id": device["id"],
            "device_name": device["name"],
            "novo_estado": new_state,
            "url_dispositivo": shelly_url
        }

    except requests.Timeout:
        return {"sucesso": False, "erro": "Timeout a comunicar com a tomada"}
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


@app.route('/')
def home():
    db = get_db()

    gestures = db.execute('SELECT * FROM Gestures ORDER BY name').fetchall()
    devices = db.execute('SELECT * FROM Devices ORDER BY name').fetchall()

    rules = db.execute('''
        SELECT Rules.id, Gestures.name AS g_name, Devices.name AS d_name, Rules.action
        FROM Rules
        JOIN Gestures ON Rules.gesture_id = Gestures.id
        JOIN Devices ON Rules.device_id = Devices.id
        ORDER BY Rules.id DESC
    ''').fetchall()

    logs = db.execute('''
        SELECT *
        FROM EventLogs
        ORDER BY id DESC
        LIMIT 10
    ''').fetchall()

    return render_template(
        'index.html',
        gestures=gestures,
        devices=devices,
        rules=rules,
        logs=logs
    )


@app.route('/add_gesture', methods=['POST'])
def add_gesture():
    gesture_name = request.form['gesture_name'].strip()

    if gesture_name:
        db = get_db()
        existing = db.execute(
            'SELECT id FROM Gestures WHERE lower(name) = lower(?)',
            (gesture_name,)
        ).fetchone()

        if not existing:
            db.execute('INSERT INTO Gestures (name) VALUES (?)', (gesture_name,))
            db.commit()

    return redirect('/')


@app.route('/delete_gesture/<int:gesture_id>', methods=['POST'])
def delete_gesture(gesture_id):
    db = get_db()
    db.execute('DELETE FROM Rules WHERE gesture_id = ?', (gesture_id,))
    db.execute('DELETE FROM Gestures WHERE id = ?', (gesture_id,))
    db.commit()
    return redirect('/')


@app.route('/add_device', methods=['POST'])
def add_device():
    device_name = request.form['device_name'].strip()
    ip_address = request.form['ip_address'].strip()

    if device_name and ip_address:
        db = get_db()
        existing = db.execute(
            'SELECT id FROM Devices WHERE lower(name) = lower(?) OR ip_address = ?',
            (device_name, ip_address)
        ).fetchone()

        if not existing:
            db.execute(
                '''
                INSERT INTO Devices (name, ip_address, current_state)
                VALUES (?, ?, ?)
                ''',
                (device_name, ip_address, 'off')
            )
            db.commit()

    return redirect('/')


@app.route('/delete_device/<int:device_id>', methods=['POST'])
def delete_device(device_id):
    db = get_db()
    db.execute('DELETE FROM Rules WHERE device_id = ?', (device_id,))
    db.execute('DELETE FROM Devices WHERE id = ?', (device_id,))
    db.commit()
    return redirect('/')


@app.route('/add_rule', methods=['POST'])
def add_rule():
    gesture_id = request.form['gesture_id']
    device_id = request.form['device_id']
    action = request.form['action']

    db = get_db()

    existing_rule = db.execute(
        '''
        SELECT id FROM Rules
        WHERE gesture_id = ? AND device_id = ?
        ''',
        (gesture_id, device_id)
    ).fetchone()

    if existing_rule:
        db.execute(
            '''
            UPDATE Rules
            SET action = ?
            WHERE id = ?
            ''',
            (action, existing_rule['id'])
        )
    else:
        db.execute(
            '''
            INSERT INTO Rules (gesture_id, device_id, action)
            VALUES (?, ?, ?)
            ''',
            (gesture_id, device_id, action)
        )

    db.commit()
    return redirect('/')


@app.route('/delete_rule/<int:rule_id>', methods=['POST'])
def delete_rule(rule_id):
    db = get_db()
    db.execute('DELETE FROM Rules WHERE id = ?', (rule_id,))
    db.commit()
    return redirect('/')


@app.route('/api/devices', methods=['GET'])
def api_devices():
    db = get_db()
    devices = db.execute(
        '''
        SELECT id, name, ip_address, current_state
        FROM Devices
        ORDER BY name
        '''
    ).fetchall()

    devices_list = []
    for d in devices:
        devices_list.append({
            "id": d["id"],
            "name": d["name"],
            "ip_address": d["ip_address"],
            "current_state": d["current_state"]
        })

    return jsonify(devices_list), 200


@app.route('/api/logs', methods=['GET'])
def api_logs():
    db = get_db()
    logs = db.execute(
        '''
        SELECT *
        FROM EventLogs
        ORDER BY id DESC
        LIMIT 10
        '''
    ).fetchall()

    logs_list = []
    for l in logs:
        logs_list.append({
            "id": l["id"],
            "event_type": l["event_type"],
            "source": l["source"],
            "gesture_name": l["gesture_name"],
            "device_name": l["device_name"],
            "action": l["action"],
            "previous_state": l["previous_state"],
            "new_state": l["new_state"],
            "created_at": l["created_at"]
        })

    return jsonify(logs_list), 200


@app.route('/api/device/<int:device_id>/action', methods=['POST'])
def api_device_action(device_id):
    data = request.get_json()

    if not data or 'action' not in data:
        return jsonify({"sucesso": False, "erro": "Nenhuma ação recebida"}), 400

    result = set_device_state(device_id, data['action'], source="manual")

    if result["sucesso"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/trigger', methods=['POST'])
def trigger_from_bracelet():
    data = request.get_json()

    if not data or 'gesto' not in data:
        return jsonify({"erro": "Nenhum gesto recebido"}), 400

    detected_gesture = data['gesto']
    db = get_db()

    rules = db.execute(
        '''
        SELECT Devices.id AS device_id,
               Rules.action
        FROM Rules
        JOIN Gestures ON Rules.gesture_id = Gestures.id
        JOIN Devices ON Rules.device_id = Devices.id
        WHERE Gestures.name = ?
        ''',
        (detected_gesture,)
    ).fetchall()

    if not rules:
        log_event(
            event_type="gesture",
            source="bracelet",
            gesture_name=detected_gesture,
            device_name="none",
            action="no_rule",
            previous_state=None,
            new_state="ignored"
        )
        return jsonify({"info": "Gesto detetado mas sem regra associada"}), 404

    results = []

    for rule in rules:
        result = set_device_state(
            rule['device_id'],
            rule['action'],
            source="bracelet",
            gesture_name=detected_gesture
        )
        results.append(result)

    return jsonify({
        "sucesso": True,
        "gesto": detected_gesture,
        "resultados": results
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)