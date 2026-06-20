# OMNIBAND — A Inteligência no teu Pulso

Projeto desenvolvido no âmbito da unidade curricular **Projeto II** (2025/2026) da Licenciatura em Engenharia Eletrotécnica e de Computadores, FCTUC.

**Grupo:** Diogo Correia, Diogo Flórido, Gonçalo Peres, Gustavo Dias

---

## 📋 Descrição

O **OmniBand** é um wearable IoT de baixo consumo, assente em TinyML, pensado para automação residencial. Uma "varinha mágica" no pulso que combina **voz** (palmas para contexto) e **gesto** (ação) com processamento local, Wi-Fi e integração com Home Assistant para controlo rápido e intuitivo.

---

## 📁 Estrutura do Repositório

```
OMNIBAND/
├── codigo_final.ino                     # Firmware PRINCIPAL do OmniBand (M5Stack CoreInk)
├── Codigo_func_total_old/               # Versão anterior do firmware (legado)
│   ├── Codigo_func_total.ino
│   └── config.h
├── OmniBand_Diagnostico_CoreInk/        # Ferramenta de diagnóstico do hardware
│   ├── OmniBand_Diagnostico_CoreInk.ino
│   └── config.h
├── RaspeberryPi/                        # SERVIDOR HUB (corre no Raspberry Pi)
│   ├── app.py                           #   API REST (Flask) + Dashboard
│   ├── smarthome.db                     #   Base de dados SQLite
│   └── templates/
│       └── index.html                   #   Dashboard web mobile-first
├── Home Assistant/                      # Configuração do Home Assistant
│   └── home-assistant/config/
│       ├── configuration.yaml           #   Configuração principal
│       ├── automations.yaml             #   Automações
│       ├── scenes.yaml                  #   Cenários
│       ├── scripts.yaml                 #   Scripts
│       └── secrets.yaml                 #   Segredos (tokens, etc.)
├── Funciona/                            # Binário funcional do firmware
│   └── palmas_micro_ecra
├── .gitignore
└── README.md
```

---

## 🚀 Como Usar

### 1️⃣ Firmware (M5StickC Plus2 / CoreInk)

1. Abre `codigo_final.ino` na Arduino IDE (com suporte ESP32/M5Stack).
2. Edita as credenciais Wi-Fi e o URL do servidor no topo do ficheiro:
   ```cpp
   const char* WIFI_SSID = "tua-rede";
   const char* WIFI_PASS = "tua-password";
   const char* SERVER_URL = "http://192.168.1.233:5000/api/trigger";
   ```
3. Compila e carrega para o dispositivo.

**Fluxo de funcionamento:**

| Estado | Descrição |
|--------|-----------|
| `IDLE` | IMU em low-power; deteta **raise-to-wake** (movimento brusco do pulso) |
| `CONTEXT` | MIC ativo; conta **palmas** para definir a divisão (1=corredor, 2=sala, 3=quarto) |
| `GESTURE` | IMU amostra movimento; classifica gesto (Cima, Baixo, RodarFora, RodarDentro) |
| `RESULT` | Envia comando HTTP POST para o hub e mostra feedback no ecrã |

**Gestos reconhecidos:**

| Gesto | Ação |
|-------|------|
| ⬆ Cima (aceleração z+) | Aumentar/subir (ex.: dimmer) |
| ⬇ Baixo (aceleração z−) | Diminuir/descer (ex.: dimmer) |
| ↻ Rodar fora (rotação +) | Ligar/acender |
| ↺ Rodar dentro (rotação −) | Desligar/apagar |

> O firmware faz auto-detecção do BMI088 (IMU) em ambas as orientações do barramento I2C e auto-calibração do microfone ao arrancar.

### 2️⃣ Hub Server (Raspberry Pi)

O servidor é uma aplicação **Flask** que corre no Raspberry Pi e faz a ponte entre o wearable e o **Home Assistant**.

```bash
cd RaspeberryPi
pip install flask requests
python3 app.py
```

O servidor inicia em `http://0.0.0.0:5000` e:
- Recebe eventos do wearable via `POST /api/trigger`
- Serve o Dashboard Web na raiz (`/`)
- Expõe API REST para gestão de dispositivos e regras
- Comunica com o Home Assistant para executar ações nos dispositivos reais

**Endpoints da API:**

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/trigger` | Wearable envia gesto detetado |
| GET | `/api/devices` | Lista dispositivos registados |
| GET | `/api/logs` | Histórico de eventos (últimos 10) |
| POST | `/api/device/<id>/action` | Controlo manual de um dispositivo |
| POST | `/api/ha/refresh` | Sincroniza estados com Home Assistant |

### 3️⃣ Dashboard Web (Configuração de Regras)

Acede pelo browser a `http://<ip-do-rpi>:5000`

**Funcionalidades:**
- **Gestos**: adicionar/remover gestos reconhecidos pelo wearable
- **Dispositivos**: registar dispositivos do Home Assistant (pelo `entity_id`)
- **Regras**: mapear cada gesto a um dispositivo e ação (on/off/toggle)
- **Histórico**: últimos eventos processados
- Integração direta com Home Assistant via REST API

### 4️⃣ Integração Home Assistant

O hub comunica com o Home Assistant através da [REST API](https://developers.home-assistant.io/docs/api/rest/). A configuração inclui:

- Ficheiros de configuração do Home Assistant em `Home Assistant/home-assistant/config/`
- Automações em `automations.yaml`
- Autenticação via token de acesso vitalício (configurado em `app.py`)

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

- **Hardware:** M5Stack CoreInk (ESP32), BMI088 (IMU), microfone U096
- **Firmware:** C++ (Arduino IDE / PlatformIO)
- **Backend:** Python (Flask), SQLite
- **Frontend:** HTML5 + CSS3 + JavaScript (vanilla)
- **Integração:** Home Assistant REST API
- **Comunicação:** Wi-Fi (HTTP REST)
- **Machine Learning:** Deteção por thresholds (implementado), Edge Impulse (planeado)

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