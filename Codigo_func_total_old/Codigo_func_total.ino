0'#include <M5Unified.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <math.h>

#include "BMI088.h"
#include "config.h"

enum SystemState {
  STATE_IDLE,
  STATE_CONTEXT,
  STATE_GESTURE,
  STATE_SENDING,
  STATE_ERROR
};

enum GestureAction {
  ACTION_NONE,
  ACTION_ON,
  ACTION_OFF,
  ACTION_DIM_UP,
  ACTION_DIM_DOWN,
  ACTION_TOGGLE
};

struct ImuSample {
  float ax;
  float ay;
  float az;
  float gx;
  float gy;
  float gz;
};

struct MicStats {
  int peakToPeak;
  int average;
  int digital;
  bool loud;
};

BMI088 bmiDefault(BMI088_ACC_ADDRESS, BMI088_GYRO_ADDRESS);
BMI088 bmiAlt(BMI088_ACC_ALT_ADDRESS, BMI088_GYRO_ALT_ADDRESS);
BMI088* bmi = &bmiDefault;

SystemState state = STATE_IDLE;
GestureAction pendingAction = ACTION_NONE;
bool imuOK = false;

String activeRoom = DEFAULT_ROOM;
unsigned long stateStartedAt = 0;
unsigned long lastImuSampleAt = 0;
unsigned long lastWifiAttemptAt = 0;

int contextPulseCount = 0;
bool previousLoud = false;
MicStats lastMic = {0, 0, 0, false};
ImuSample lastImu = {0, 0, 0, 0, 0, 0};

float maxGx = 0;
float minGx = 0;
float maxGy = 0;
float minGy = 0;
float maxGz = 0;
float minGz = 0;

const unsigned long CONTEXT_WINDOW_MS = 2600;
const unsigned long GESTURE_WINDOW_MS = 2200;
const unsigned long IDLE_IMU_INTERVAL_MS = 80;
const unsigned long GESTURE_IMU_INTERVAL_MS = 35;
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000;

String stateName(SystemState value) {
  switch (value) {
    case STATE_IDLE:
      return "idle";
    case STATE_CONTEXT:
      return "contexto";
    case STATE_GESTURE:
      return "gesto";
    case STATE_SENDING:
      return "envio";
    case STATE_ERROR:
      return "erro";
  }
  return "desconhecido";
}

String actionName(GestureAction action) {
  switch (action) {
    case ACTION_ON:
      return "on";
    case ACTION_OFF:
      return "off";
    case ACTION_DIM_UP:
      return "dim_up";
    case ACTION_DIM_DOWN:
      return "dim_down";
    case ACTION_TOGGLE:
      return "toggle";
    case ACTION_NONE:
      return "none";
  }
  return "none";
}

String roomFromPulses(int pulses) {
  if (pulses <= 1) {
    return "corredor";
  }
  if (pulses == 2) {
    return "sala";
  }
  return "quarto";
}

String nextRoom(String current) {
  if (current == "corredor") {
    return "sala";
  }
  if (current == "sala") {
    return "quarto";
  }
  return "corredor";
}

void drawStatus(const String& line1 = "", const String& line2 = "") {
  M5.Display.fillScreen(TFT_WHITE);
  M5.Display.setTextColor(TFT_BLACK, TFT_WHITE);
  M5.Display.setTextSize(2);
  M5.Display.setCursor(8, 10);
  M5.Display.println("OmniBand");

  M5.Display.setTextSize(1);
  M5.Display.setCursor(8, 42);
  M5.Display.printf("Estado: %s\n", stateName(state).c_str());
  M5.Display.printf("Sala: %s\n", activeRoom.c_str());
  M5.Display.printf("IMU: %s\n", imuOK ? "OK" : "N/D");
  M5.Display.printf("WiFi: %s\n", WiFi.status() == WL_CONNECTED ? "OK" : "OFF");
  M5.Display.printf("Mic p2p: %d\n", lastMic.peakToPeak);

  if (line1.length() > 0) {
    M5.Display.setCursor(8, 126);
    M5.Display.println(line1);
  }
  if (line2.length() > 0) {
    M5.Display.setCursor(8, 144);
    M5.Display.println(line2);
  }

  M5.Display.setCursor(8, 176);
  M5.Display.println("Btn: sala+janela");
}

void enterState(SystemState next, const String& line1 = "", const String& line2 = "") {
  state = next;
  stateStartedAt = millis();

  if (state == STATE_CONTEXT) {
    contextPulseCount = 0;
    previousLoud = false;
  }

  if (state == STATE_GESTURE) {
    pendingAction = ACTION_NONE;
    maxGx = minGx = maxGy = minGy = maxGz = minGz = 0;
  }

  drawStatus(line1, line2);
}

bool connectWiFi(unsigned long timeoutMs = 3500) {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }
  if (String(WIFI_SSID).length() == 0) {
    return false;
  }
  if (millis() - lastWifiAttemptAt < WIFI_RETRY_INTERVAL_MS) {
    return false;
  }

  lastWifiAttemptAt = millis();
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < timeoutMs) {
    delay(100);
  }
  return WiFi.status() == WL_CONNECTED;
}

bool probeImuWithPins(uint8_t sda, uint8_t scl) {
  Wire.end();
  delay(40);
  Wire.begin(sda, scl);
  Wire.setClock(400000);

  BMI088* candidates[] = {&bmiDefault, &bmiAlt};
  for (uint8_t i = 0; i < 2; i++) {
    if (candidates[i]->isConnection()) {
      bmi = candidates[i];
      bmi->initialize();
      bmi->setAccScaleRange(RANGE_3G);
      bmi->setGyroScaleRange(RANGE_500);
      bmi->setAccOutputDataRate(ODR_100);
      bmi->setGyroOutputDataRate(ODR_100_BW_32);
      Serial.printf("BMI088 OK em SDA=%u SCL=%u\n", sda, scl);
      return true;
    }
  }
  return false;
}

bool initImu() {
  if (probeImuWithPins(I2C_PRIMARY_SDA, I2C_PRIMARY_SCL)) {
    return true;
  }
  if (probeImuWithPins(I2C_FALLBACK_SDA, I2C_FALLBACK_SCL)) {
    return true;
  }
  Serial.println("BMI088 nao encontrado");
  return false;
}

bool readImu(ImuSample& sample) {
  if (!imuOK) {
    return false;
  }
  bmi->getAcceleration(&sample.ax, &sample.ay, &sample.az);
  bmi->getGyroscope(&sample.gx, &sample.gy, &sample.gz);
  return true;
}

bool isRaiseToWake(const ImuSample& sample) {
  float gyroEnergy = fabs(sample.gx) + fabs(sample.gy) + fabs(sample.gz);
  float accelNorm = sqrt(sample.ax * sample.ax + sample.ay * sample.ay + sample.az * sample.az);
  return gyroEnergy > WAKE_GYRO_THRESHOLD || fabs(accelNorm - 1000.0f) > WAKE_ACCEL_DELTA_THRESHOLD;
}

MicStats sampleMic(unsigned long durationMs = 80) {
  int minValue = 4095;
  int maxValue = 0;
  long sum = 0;
  int samples = 0;
  int digitalHits = 0;
  unsigned long startedAt = millis();

  while (millis() - startedAt < durationMs) {
    int analogValue = analogRead(MIC_ANALOG_PIN);
    int digitalValue = digitalRead(MIC_DIGITAL_PIN);

    minValue = min(minValue, analogValue);
    maxValue = max(maxValue, analogValue);
    sum += analogValue;
    samples++;
    if (digitalValue == HIGH) {
      digitalHits++;
    }

    delayMicroseconds(650);
  }

  MicStats stats;
  stats.peakToPeak = maxValue - minValue;
  stats.average = samples > 0 ? sum / samples : 0;
  stats.digital = samples > 0 && digitalHits > samples / 3 ? HIGH : LOW;
  stats.loud = stats.peakToPeak > AUDIO_PULSE_THRESHOLD || stats.digital == HIGH;
  return stats;
}

void considerGesture(float value, GestureAction action, float& bestValue, GestureAction& bestAction) {
  if (fabs(value) > fabs(bestValue)) {
    bestValue = value;
    bestAction = action;
  }
}

GestureAction classifyGesture() {
  float bestValue = 0;
  GestureAction bestAction = ACTION_NONE;

  considerGesture(maxGz, ACTION_ON, bestValue, bestAction);
  considerGesture(minGz, ACTION_OFF, bestValue, bestAction);
  considerGesture(maxGy, ACTION_DIM_UP, bestValue, bestAction);
  considerGesture(minGy, ACTION_DIM_DOWN, bestValue, bestAction);
  considerGesture(maxGx, ACTION_TOGGLE, bestValue, bestAction);
  considerGesture(minGx, ACTION_TOGGLE, bestValue, bestAction);

  if (fabs(bestValue) < GESTURE_GYRO_THRESHOLD) {
    return ACTION_NONE;
  }
  return bestAction;
}

String commandPayload(GestureAction action) {
  String payload = "{";
  payload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
  payload += "\"room\":\"" + activeRoom + "\",";
  payload += "\"device\":\"light\",";
  payload += "\"action\":\"" + actionName(action) + "\",";
  payload += "\"battery\":" + String(M5.Power.getBatteryLevel()) + ",";
  payload += "\"rssi\":" + String(WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0) + ",";
  payload += "\"metrics\":{";
  payload += "\"mic_peak\":" + String(lastMic.peakToPeak) + ",";
  payload += "\"mic_avg\":" + String(lastMic.average) + ",";
  payload += "\"mic_digital\":" + String(lastMic.digital) + ",";
  payload += "\"ax\":" + String(lastImu.ax, 2) + ",";
  payload += "\"ay\":" + String(lastImu.ay, 2) + ",";
  payload += "\"az\":" + String(lastImu.az, 2) + ",";
  payload += "\"gx\":" + String(lastImu.gx, 2) + ",";
  payload += "\"gy\":" + String(lastImu.gy, 2) + ",";
  payload += "\"gz\":" + String(lastImu.gz, 2);
  payload += "}}";
  return payload;
}

bool sendCommand(GestureAction action) {
  if (action == ACTION_NONE) {
    Serial.println("Sem gesto reconhecido");
    return false;
  }
  if (!connectWiFi()) {
    Serial.println("WiFi indisponivel");
    return false;
  }

  HTTPClient http;
  http.begin(HUB_EVENT_URL);
  http.addHeader("Content-Type", "application/json");
  String payload = commandPayload(action);
  int code = http.POST(payload);
  String response = http.getString();
  http.end();

  Serial.printf("POST %s -> %d %s\n", HUB_EVENT_URL, code, response.c_str());
  return code >= 200 && code < 300;
}

void handleButtons() {
  if (M5.BtnA.wasPressed()) {
    activeRoom = nextRoom(activeRoom);
    if (state == STATE_IDLE) {
      enterState(STATE_GESTURE, "Modo manual", activeRoom);
    } else {
      drawStatus("Sala manual", activeRoom);
    }
  }
}

void handleIdle() {
  if (millis() - lastImuSampleAt < IDLE_IMU_INTERVAL_MS) {
    return;
  }
  lastImuSampleAt = millis();

  if (!readImu(lastImu)) {
    return;
  }

  if (isRaiseToWake(lastImu)) {
    Serial.println("Raise-to-wake detetado");
    enterState(STATE_CONTEXT, "Diz/pulsa contexto", "1=cor 2=sala 3=quarto");
  }
}

void handleContext() {
  lastMic = sampleMic();
  bool risingEdge = lastMic.loud && !previousLoud;
  previousLoud = lastMic.loud;

  if (risingEdge) {
    contextPulseCount++;
    Serial.printf("Pulso de contexto: %d\n", contextPulseCount);
  }

  if (millis() - stateStartedAt >= CONTEXT_WINDOW_MS) {
    activeRoom = roomFromPulses(contextPulseCount);
    enterState(STATE_GESTURE, "Contexto: " + activeRoom, "Faz o gesto");
  }
}

void handleGesture() {
  if (millis() - lastImuSampleAt >= GESTURE_IMU_INTERVAL_MS) {
    lastImuSampleAt = millis();
    if (readImu(lastImu)) {
      maxGx = max(maxGx, lastImu.gx);
      minGx = min(minGx, lastImu.gx);
      maxGy = max(maxGy, lastImu.gy);
      minGy = min(minGy, lastImu.gy);
      maxGz = max(maxGz, lastImu.gz);
      minGz = min(minGz, lastImu.gz);
    }
  }

  if (millis() - stateStartedAt >= GESTURE_WINDOW_MS) {
    pendingAction = classifyGesture();
    enterState(STATE_SENDING, "Acao: " + actionName(pendingAction), "A enviar...");
  }
}

void handleSending() {
  bool ok = sendCommand(pendingAction);
  if (ok) {
    enterState(STATE_IDLE, "Comando enviado", activeRoom + ":" + actionName(pendingAction));
  } else {
    enterState(STATE_IDLE, "Falha no envio/gesto", actionName(pendingAction));
  }
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);

  Serial.begin(115200);
  delay(200);
  Serial.println("OmniBand CoreInk boot");

  pinMode(MIC_DIGITAL_PIN, INPUT_PULLUP);
  pinMode(MIC_ANALOG_PIN, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(MIC_ANALOG_PIN, ADC_11db);

  imuOK = initImu();
  connectWiFi(5000);
  enterState(STATE_IDLE, "Pronto", "Raise-to-wake");
}

void loop() {
  M5.update();
  handleButtons();

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  switch (state) {
    case STATE_IDLE:
      handleIdle();
      break;
    case STATE_CONTEXT:
      handleContext();
      break;
    case STATE_GESTURE:
      handleGesture();
      break;
    case STATE_SENDING:
      handleSending();
      break;
    case STATE_ERROR:
      enterState(STATE_IDLE);
      break;
  }

  delay(5);
}
