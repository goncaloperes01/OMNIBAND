/**
 * OmniBand Dashboard – Mobile App Logic
 * =========================================
 * Communicates with the hub server (hub_server.py) via REST API.
 *
 * Hub server expected at HUB_URL (change to your RPi IP).
 */

// ── CONFIG ──────────────────────────────────────────────
const HUB_URL = window.location.origin;  // Same origin (works when served via hub server)
// Fallback: use the device address. Uncomment and change if needed:
// const HUB_URL = "http://192.168.1.50:8080";

const POLL_INTERVAL_MS = 2000;

// ── STATE ───────────────────────────────────────────────
let devices = {};
let wearableStatus = null;
let historyLog = [];

// ── DOM REFS ────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const roomsContainer = $("rooms-container");
const wearableCard = $("wearable-card");
const historyList = $("history-list");
const controlPanel = $("control-panel");
const toastEl = $("toast");
const activeRoomName = $("active-room-name");
const wearableIndicator = $("wearable-indicator");
const batteryValue = $("battery-value");

// ── TOAST ───────────────────────────────────────────────
let toastTimeout = null;

function showToast(message, type = "") {
  toastEl.textContent = message;
  toastEl.className = "toast " + type;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {
    toastEl.classList.add("hidden");
  }, 3000);
  // force reflow to restart animation
  void toastEl.offsetWidth;
  toastEl.classList.remove("hidden");
}

// ── TABS ────────────────────────────────────────────────
document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $(btn.dataset.tab).classList.add("active");
  });
});

// ── API CALLS ──────────────────────────────────────────
async function apiFetch(path, options = {}) {
  try {
    const url = HUB_URL + path;
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    return await res.json();
  } catch (err) {
    console.warn(`API ${path} failed:`, err);
    return null;
  }
}

async function fetchDevices() {
  const data = await apiFetch("/api/devices");
  if (data && data.rooms) {
    devices = data.rooms;
  }
}

async function fetchStatus() {
  const data = await apiFetch("/api/status");
  if (data) {
    wearableStatus = data.wearable || null;
    historyLog = data.history || [];
  }
}

async function sendControl(room, action, brightness = null) {
  const body = { room, action };
  if (brightness !== null) {
    body.brightness = brightness;
  }
  const result = await apiFetch("/api/control", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (result && result.status === "ok") {
    showToast(`✅ ${room}: ${action}`, "success");
  } else {
    showToast(`❌ ${result?.message || "Erro"}`, "error");
  }
  await pollAll();
}

async function pollAll() {
  await Promise.all([fetchDevices(), fetchStatus()]);
  renderAll();
}

// ── RENDER ──────────────────────────────────────────────
function renderAll() {
  renderRooms();
  renderStatus();
  renderHistory();
  renderControlPanel();
  renderAppbar();
}

function roomIcon(room) {
  const icons = { corredor: "fa-door-open", sala: "fa-couch", quarto: "fa-bed" };
  return icons[room] || "fa-lightbulb";
}

function roomNamePt(room) {
  const names = { corredor: "Corredor", sala: "Sala", quarto: "Quarto" };
  return names[room] || room;
}

function renderRooms() {
  if (!devices || Object.keys(devices).length === 0) {
    roomsContainer.innerHTML = `<div class="room-card"><p style="color:var(--text-dim);text-align:center;">A aguardar dados do hub...</p></div>`;
    return;
  }

  let html = "";
  let activeRoom = wearableStatus?.active_room || "corredor";

  for (const [room, dev] of Object.entries(devices)) {
    const isOn = dev.light;
    const brightness = dev.brightness || 100;
    const isActive = room === activeRoom;

    html += `
      <div class="room-card ${isOn ? "on" : ""}" data-room="${room}">
        <div class="room-header">
          <div class="room-name">
            <i class="fas ${roomIcon(room)}"></i>
            ${roomNamePt(room)}
            ${isActive ? '<span style="font-size:10px;color:var(--accent);margin-left:6px;">● ativo</span>' : ""}
          </div>
          <span class="room-status-badge ${isOn ? "on" : "off"}">
            ${isOn ? "Ligado" : "Desligado"}
          </span>
        </div>

        <div class="room-controls">
          <button class="room-toggle ${isOn ? "on" : ""}" 
                  onclick="sendControl('${room}','toggle')">
          </button>

          <div class="room-actions">
            <button class="btn-icon" onclick="sendControl('${room}','on')" title="Ligar">
              <i class="fas fa-power-off"></i>
            </button>
            <button class="btn-icon" onclick="sendControl('${room}','off')" title="Desligar">
              <i class="fas fa-power-off" style="opacity:0.4;"></i>
            </button>
            <button class="btn-icon" onclick="sendControl('${room}','dim_up')" title="Mais luz">
              <i class="fas fa-sun"></i>
            </button>
            <button class="btn-icon" onclick="sendControl('${room}','dim_down')" title="Menos luz">
              <i class="fas fa-moon"></i>
            </button>
          </div>
        </div>

        <input type="range" class="brightness-slider" min="0" max="100" value="${brightness}"
               oninput="sendControl('${room}','set_brightness', parseInt(this.value))"
               ${isOn ? "" : "disabled"}>
      </div>
    `;
  }

  roomsContainer.innerHTML = html;

  // Update banner
  activeRoomName.textContent = roomNamePt(activeRoom);
  const lastSeen = wearableStatus?.last_seen_ago;
  $("active-room-time").textContent =
    wearableStatus?.online ? `há ${lastSeen || 0}s` : "offline";
}

function renderStatus() {
  if (!wearableStatus) {
    wearableCard.innerHTML = `<p style="color:var(--text-dim);">A aguardar dados...</p>`;
    return;
  }

  const ws = wearableStatus;
  const online = ws.online;
  wearableCard.innerHTML = `
    <div class="status-grid">
      <div class="status-item">
        <span class="status-label">Conexão</span>
        <span class="status-value ${online ? "online" : "offline"}">
          ${online ? "Online" : "Offline"}
        </span>
      </div>
      <div class="status-item">
        <span class="status-label">Bateria</span>
        <span class="status-value">${ws.battery || "--"}%</span>
      </div>
      <div class="status-item">
        <span class="status-label">Wi-Fi (RSSI)</span>
        <span class="status-value">${ws.rssi || "--"} dBm</span>
      </div>
      <div class="status-item">
        <span class="status-label">Divisão Ativa</span>
        <span class="status-value" style="color:var(--accent);">
          ${roomNamePt(ws.active_room || "---")}
        </span>
      </div>
      <div class="status-item">
        <span class="status-label">Última Atualização</span>
        <span class="status-value" style="font-size:13px;">
          ${ws.last_seen ? new Date(ws.last_seen * 1000).toLocaleTimeString() : "---"}
        </span>
      </div>
    </div>
  `;
}

function renderHistory() {
  if (!historyLog || historyLog.length === 0) {
    historyList.innerHTML = `<div class="history-item" style="justify-content:center;color:var(--text-dim);">Nenhum comando registado</div>`;
    return;
  }

  historyList.innerHTML = historyLog
    .slice(0, 20)
    .map((entry) => {
      const actionClass = entry.action === "on" || entry.action === "toggle" ? "on" : "off";
      return `
        <div class="history-item">
          <span class="history-time">${entry.timestamp || "--"}</span>
          <span class="history-room">${roomNamePt(entry.room)}</span>
          <span class="history-action ${actionClass}">${entry.action}</span>
        </div>
      `;
    })
    .join("");
}

function renderControlPanel() {
  const roomOptions = Object.keys(devices)
    .map((r) => `<option value="${r}">${roomNamePt(r)}</option>`)
    .join("");

  controlPanel.innerHTML = `
    <div class="control-group">
      <label>Divisão</label>
      <select id="ctrl-room">${roomOptions}</select>
    </div>

    <div class="control-group">
      <label>Ações rápidas</label>
      <div class="control-buttons">
        <button onclick="sendCtrlAction('toggle')">⟳ Toggle</button>
        <button onclick="sendCtrlAction('on')">🔌 Ligar</button>
        <button onclick="sendCtrlAction('off')">🔌 Desligar</button>
        <button onclick="sendCtrlAction('dim_up')">☀️ Mais luz</button>
        <button onclick="sendCtrlAction('dim_down')">🌙 Menos luz</button>
      </div>
    </div>
  `;
}

function sendCtrlAction(action) {
  const room = document.getElementById("ctrl-room").value;
  if (!room) return;
  sendControl(room, action);
}

function renderAppbar() {
  const online = wearableStatus?.online || false;
  const batt = wearableStatus?.battery;

  wearableIndicator.className = "status-dot " + (online ? "online" : "offline");
  batteryValue.textContent = batt !== undefined && batt !== null ? batt : "--";
}

// ── INIT ────────────────────────────────────────────────
function init() {
  // Poll immediately, then every POLL_INTERVAL_MS
  pollAll();
  setInterval(pollAll, POLL_INTERVAL_MS);
}

// Start when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}