# OMNIBAND — A Inteligência no teu Pulso

Projeto desenvolvido no âmbito da unidade curricular **Projeto II** (2025/2026) da Licenciatura em Engenharia Eletrotécnica e de Computadores, FCTUC.

**Grupo:** Diogo Correia, Diogo Flórido, Gonçalo Peres, Gustavo Dias

---

## 📋 Descrição

O **OmniBand** é um wearable IoT de baixo consumo, assente em TinyML, pensado para automação residencial. Uma "varinha mágica" no pulso que combina **voz** (contexto) e **gesto** (ação) com processamento local, com Wi-Fi e uma app móvel para controlo rápido e intuitivo.

---

## 📁 Estrutura do Repositório

```
OMNIBAND/
├── Codigo_func_total/               # Firmware PRINCIPAL do OmniBand
│   ├── Codigo_func_total.ino        #   Máquina de estados completa
│   └── config.h                     #   Configuração (Wi-Fi, pins, thresholds)
│
├── OmniBand_Diagnostico_CoreInk/    # Ferramenta de diagnóstico
│   ├── OmniBand_Diagnostico_CoreInk.ino
│   └── config.h
│
├── hub_server/                      # SERVIDOR HUB (corre no Raspberry Pi)
│   └── hub_server.py               #   API REST + serve App Móvel
│
├── app_mobile/                      # DASHBOARD MOBILE (Web App)
│   ├── index.html                  #   Página principal
│   ├── style.css                   #   Estilos mobile-first (dark theme)
│   ├── app.js                      #   Lógica JS (polling + controlo)
│   └── manifest.json              #   PWA manifest
│
├── codigo_teste.ino                 # Sketch de teste (MIC + IMU)
├── testemqtt.ino                    # Sketch de teste MQTT
└── README.md
```

---

## 🚀 Como Usar

### 1️⃣ Firmware (M5StickC Plus2 / CoreInk)

1. Abre `Codigo_func_total/Codigo_func_total.ino` na Arduino IDE (com suporte ESP32/M5Stack).
2. Edita `config.h` com os dados da tua rede Wi-Fi e IP do hub:
   ```cpp
   #define WIFI_SSID "tua-rede"
   #define WIFI_PASSWORD "tua-password"
   #define HUB_EVENT_URL "http://192.168.1.50:8080/api/event"
   ```
3. Compila e carrega para o dispositivo.

**Fluxo de funcionamento:**
- `IDLE` → IMU em low-power; deteta **raise-to-wake**
- `CONTEXT` → MIC ativo durante 2.6s; conta pulsos de áudio (1=corredor, 2=sala, 3=quarto)
- `GESTURE` → IMU amostra durante 2.2s; classifica gesto (gz=ON/OFF, gy=DIM, gx=TOGGLE)
- `SENDING` → Envia comando HTTP POST para o hub
- Volta a `IDLE`

### 2️⃣ Hub Server (Raspberry Pi)

```bash
cd hub_server
python3 hub_server.py
```

O servidor inicia em `http://0.0.0.0:8080` e:
- Recebe eventos do wearable via `POST /api/event`
- Serve a App Móvel na raiz (`/`)
- Expõe API REST para o dashboard

**Endpoints:**
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/event` | Wearable envia comando |
| GET | `/api/devices` | Estado de todas as divisões |
| POST | `/api/control` | App envia comando manual |
| GET | `/api/status` | Estado do wearable + histórico |

### 3️⃣ App Móvel (Dashboard)

Acede pelo browser do telemóvel a `http://<ip-do-rpi>:8080`

**Funcionalidades:**
- **Divisões**: toggle on/off, dimmer, indicador da sala ativa
- **Estado**: wearable online/offline, bateria, RSSI, sala ativa
- **Controlo manual**: seleciona divisão e envia comandos
- **Histórico**: últimos comandos executados
- Tempo real (polling a cada 2s)

---

## 📦 Entregas Submetidas

| Ref. | Atividade | Título | Data |
|------|-----------|--------|------|
| E1 | A1 | Proposta de Projeto | 01/03/2026 |
| E2 | A1 | ConOps | 15/03/2026 |
| E3 | A1 | SRS | 29/03/2026 |
| E4 | A5 | Test Plan | 19/04/2026 |
| E5 | A1, A3 | System Architecture | 03/05/2026 |
| E6 | A6 | **Relatório Final + Vídeo** | **21/06/2026** |
| E7 | A6 | **Apresentação + Demo Day** | **25/06/2026** |

---

## 🧰 Tecnologias

- **Hardware:** M5StickC Plus2 / CoreInk (ESP32), BMI088 (IMU), microfone U096
- **Firmware:** C++ (Arduino IDE / PlatformIO)
- **Backend:** Python (http.server nativo)
- **Frontend:** HTML5 + CSS3 + JavaScript (vanilla, PWA-ready)
- **Comunicação:** Wi-Fi (HTTP REST)
- **Machine Learning:** Edge Impulse (planeado) / thresholds manuais (implementado)

---

## 👥 Autores

| Nome | Nº Aluno | Email |
|------|----------|-------|
| Diogo Correia | 2023215978 | diogolopescorreia28@gmail.com |
| Diogo Flórido | 2020233528 | diogo.florido@student.uc.pt |
| Gonçalo Peres | 2023212120 | goncaloperes02@gmail.com |
| Gustavo Dias | 2023212954 | gustavogaspardias@gmail.com |

---

## 📄 Licença

Projeto académico sem fins comerciais.