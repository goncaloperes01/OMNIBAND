#include <M5Unified.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ctype.h>

#include "BMI088.h"
#include "config.h"

struct MicStats {
  int minValue;
  int maxValue;
  int peakToPeak;
  int average;
  int digitalRaw;
  bool digitalActive;
  bool loud;
};

struct ImuSample {
  float ax;
  float ay;
  float az;
  float gx;
  float gy;
  float gz;
  int16_t temp;
};

BMI088 bmiDefault(BMI088_ACC_ADDRESS, BMI088_GYRO_ADDRESS);
BMI088 bmiAlt(BMI088_ACC_ALT_ADDRESS, BMI088_GYRO_ALT_ADDRESS);
BMI088* bmi = &bmiDefault;

char activeMode = 'q';
bool imuReady = false;
unsigned long lastPrintAt = 0;

bool micDigitalIsActive(int value) {
#if MIC_DIGITAL_ACTIVE_LOW
  return value == LOW;
#else
  return value == HIGH;
#endif
}

void drawTitle(const String& title, const String& line = "") {
  M5.Display.fillScreen(TFT_WHITE);
  M5.Display.setTextColor(TFT_BLACK, TFT_WHITE);
  M5.Display.setTextSize(2);
  M5.Display.setCursor(8, 10);
  M5.Display.println("Diag CoreInk");
  M5.Display.setTextSize(1);
  M5.Display.setCursor(8, 48);
  M5.Display.println(title);
  if (line.length() > 0) {
    M5.Display.setCursor(8, 72);
    M5.Display.println(line);
  }
  M5.Display.setCursor(8, 176);
  M5.Display.println("Serial: m i s w h b a q");
}

void printPinout() {
  Serial.println();
  Serial.println("===== OmniBand Diagnostico CoreInk =====");
  Serial.println("Baud: 115200");
  Serial.println("CoreInk HY2.0-4P: preto=GND, vermelho=5V, amarelo=G32, branco=G33");
  Serial.println("BMI088: branco=SDA=G33, amarelo=SCL=G32");
  Serial.println("U096: amarelo=digital=G26, branco=analogico=G36, vermelho=5V, preto=GND");
  Serial.printf("MIC_DIGITAL_ACTIVE_LOW=%d | AUDIO_PULSE_THRESHOLD=%d\n",
                MIC_DIGITAL_ACTIVE_LOW,
                AUDIO_PULSE_THRESHOLD);
  Serial.println();
}

void printMenu() {
  Serial.println("Comandos:");
  Serial.println("  m - testar microfone U096");
  Serial.println("  i - testar BMI088");
  Serial.println("  s - scan I2C");
  Serial.println("  w - testar WiFi");
  Serial.println("  h - testar POST para hub Raspberry Pi");
  Serial.println("  b - testar botoes/dial do CoreInk");
  Serial.println("  a - teste combinado MIC + IMU");
  Serial.println("  p - mostrar pinout");
  Serial.println("  q - parar e mostrar menu");
  Serial.println();
}

int scanI2CBusAtPins(uint8_t sda, uint8_t scl) {
  Serial.printf("[i2c] Scan em SDA=G%d SCL=G%d\n", sda, scl);
  Wire.end();
  delay(40);
  Wire.begin(sda, scl);
  Wire.setClock(400000);

  int count = 0;
  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.printf("[i2c] Encontrado: 0x%02X\n", address);
      count++;
    }
  }

  if (count == 0) {
    Serial.println("[i2c] Nenhum dispositivo encontrado.");
  } else {
    Serial.printf("[i2c] Total: %d dispositivo(s). BMI088 esperado: 0x19 + 0x69 ou 0x18 + 0x68.\n", count);
  }
  return count;
}

void scanI2CBus() {
  int primaryCount = scanI2CBusAtPins(I2C_SDA_PIN, I2C_SCL_PIN);
  int fallbackCount = scanI2CBusAtPins(I2C_FALLBACK_SDA_PIN, I2C_FALLBACK_SCL_PIN);

  if (primaryCount == 0 && fallbackCount > 0) {
    Serial.println("[i2c] Nota: apareceu apenas na orientacao trocada. Reve SDA/SCL ou ajusta config.h.");
  }
}

bool probeImuAtPins(uint8_t sda, uint8_t scl) {
  Wire.end();
  delay(40);
  Wire.begin(sda, scl);
  Wire.setClock(400000);

  BMI088* candidates[] = {&bmiDefault, &bmiAlt};
  const char* names[] = {"default 0x19/0x69", "alt 0x18/0x68"};

  for (uint8_t i = 0; i < 2; i++) {
    if (candidates[i]->isConnection()) {
      bmi = candidates[i];
      bmi->initialize();
      bmi->setAccScaleRange(RANGE_3G);
      bmi->setGyroScaleRange(RANGE_500);
      bmi->setAccOutputDataRate(ODR_100);
      bmi->setGyroOutputDataRate(ODR_100_BW_32);
      Serial.printf("[imu] BMI088 ligado (%s) em SDA=G%d SCL=G%d\n", names[i], sda, scl);
      return true;
    }
  }

  return false;
}

bool initImu() {
  if (probeImuAtPins(I2C_SDA_PIN, I2C_SCL_PIN)) {
    return true;
  }
  if (probeImuAtPins(I2C_FALLBACK_SDA_PIN, I2C_FALLBACK_SCL_PIN)) {
    return true;
  }

  Serial.println("[imu] BMI088 nao encontrado. Faz primeiro 's' para scan I2C.");
  return false;
}

bool readImu(ImuSample& sample) {
  if (!imuReady) {
    imuReady = initImu();
  }
  if (!imuReady) {
    return false;
  }

  bmi->getAcceleration(&sample.ax, &sample.ay, &sample.az);
  bmi->getGyroscope(&sample.gx, &sample.gy, &sample.gz);
  sample.temp = bmi->getTemperature();
  return true;
}

MicStats sampleMic(unsigned long durationMs = 100) {
  MicStats stats = {4095, 0, 0, 0, 0, false, false};
  long sum = 0;
  int samples = 0;
  int digitalActiveHits = 0;
  int lastDigitalRaw = LOW;

  unsigned long startedAt = millis();
  while (millis() - startedAt < durationMs) {
    int analogValue = analogRead(MIC_ANALOG_PIN);
    int digitalValue = digitalRead(MIC_DIGITAL_PIN);

    stats.minValue = min(stats.minValue, analogValue);
    stats.maxValue = max(stats.maxValue, analogValue);
    sum += analogValue;
    samples++;
    lastDigitalRaw = digitalValue;
    if (micDigitalIsActive(digitalValue)) {
      digitalActiveHits++;
    }

    delayMicroseconds(650);
  }

  stats.peakToPeak = stats.maxValue - stats.minValue;
  stats.average = samples > 0 ? sum / samples : 0;
  stats.digitalRaw = lastDigitalRaw;
  stats.digitalActive = samples > 0 && digitalActiveHits > samples / 3;
  stats.loud = stats.peakToPeak > AUDIO_PULSE_THRESHOLD || stats.digitalActive;
  return stats;
}

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[wifi] Ja ligado ip=%s rssi=%d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    return true;
  }
  if (String(WIFI_SSID).length() == 0) {
    Serial.println("[wifi] WIFI_SSID vazio no config.h deste sketch.");
    return false;
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[wifi] A ligar a \"%s\"...\n", WIFI_SSID);

  unsigned long startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 12000) {
    Serial.print(".");
    delay(500);
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[wifi] OK ip=%s rssi=%d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    return true;
  }

  Serial.println("[wifi] Falhou. Confirma SSID/password e se a rede e 2.4 GHz.");
  return false;
}

void postHubTest() {
  if (!connectWiFi()) {
    return;
  }

  HTTPClient http;
  http.begin(HUB_EVENT_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{";
  payload += "\"device_id\":\"diagnostico-coreink\",";
  payload += "\"room\":\"teste\",";
  payload += "\"device\":\"light\",";
  payload += "\"action\":\"toggle\",";
  payload += "\"metrics\":{\"source\":\"diagnostico\"}";
  payload += "}";

  Serial.printf("[hub] POST %s\n", HUB_EVENT_URL);
  Serial.printf("[hub] payload=%s\n", payload.c_str());
  int code = http.POST(payload);
  String response = http.getString();
  http.end();

  Serial.printf("[hub] HTTP %d response=%s\n", code, response.c_str());
}

void setMode(char mode) {
  activeMode = mode;
  lastPrintAt = 0;

  switch (mode) {
    case 'm':
      drawTitle("Teste MIC U096", "Sopra/bate palmas perto do mic");
      Serial.println("[mode] Microfone U096");
      break;
    case 'i':
      drawTitle("Teste BMI088", "Mexe/roda o modulo IMU");
      Serial.println("[mode] BMI088");
      imuReady = initImu();
      break;
    case 's':
      drawTitle("Scan I2C", "Ver Serial Monitor");
      scanI2CBus();
      activeMode = 'q';
      printMenu();
      break;
    case 'w':
      drawTitle("Teste WiFi", "Ver Serial Monitor");
      connectWiFi();
      activeMode = 'q';
      printMenu();
      break;
    case 'h':
      drawTitle("Teste Hub HTTP", "Ver Serial Monitor");
      postHubTest();
      activeMode = 'q';
      printMenu();
      break;
    case 'b':
      drawTitle("Teste botoes", "Prime botoes/dial");
      Serial.println("[mode] Botoes CoreInk");
      break;
    case 'a':
      drawTitle("Teste MIC + IMU", "Mexe e faz som");
      Serial.println("[mode] Combinado MIC + IMU");
      imuReady = initImu();
      break;
    case 'p':
      printPinout();
      activeMode = 'q';
      printMenu();
      break;
    case 'q':
    default:
      activeMode = 'q';
      drawTitle("Parado", "Escolhe teste no Serial");
      printMenu();
      break;
  }
}

void handleSerialInput() {
  while (Serial.available() > 0) {
    char c = (char)tolower(Serial.read());
    if (c == '\n' || c == '\r' || c == ' ') {
      continue;
    }
    setMode(c);
  }
}

void loopMic() {
  if (millis() - lastPrintAt < 250) {
    return;
  }
  lastPrintAt = millis();

  MicStats mic = sampleMic(100);
  Serial.printf("[mic] min=%d max=%d p2p=%d avg=%d digital_raw=%d digital_active=%d loud=%d\n",
                mic.minValue,
                mic.maxValue,
                mic.peakToPeak,
                mic.average,
                mic.digitalRaw,
                mic.digitalActive,
                mic.loud);
}

void loopImu() {
  if (millis() - lastPrintAt < 150) {
    return;
  }
  lastPrintAt = millis();

  ImuSample imu;
  if (!readImu(imu)) {
    delay(500);
    return;
  }

  Serial.printf("[imu] ax=%.2f ay=%.2f az=%.2f gx=%.2f gy=%.2f gz=%.2f temp=%d\n",
                imu.ax,
                imu.ay,
                imu.az,
                imu.gx,
                imu.gy,
                imu.gz,
                imu.temp);
}

void loopButtons() {
  if (millis() - lastPrintAt < 200) {
    return;
  }
  lastPrintAt = millis();

  Serial.printf("[btn] BtnA_pressed=%d raw_user_G5=%d dial_up_G37=%d dial_mid_G38=%d dial_down_G39=%d\n",
                M5.BtnA.wasPressed(),
                digitalRead(5),
                digitalRead(37),
                digitalRead(38),
                digitalRead(39));
}

void loopAll() {
  if (millis() - lastPrintAt < 400) {
    return;
  }
  lastPrintAt = millis();

  MicStats mic = sampleMic(80);
  ImuSample imu;
  bool imuOk = readImu(imu);

  Serial.printf("[all] mic_p2p=%d mic_avg=%d mic_dig=%d loud=%d imu_ok=%d",
                mic.peakToPeak,
                mic.average,
                mic.digitalActive,
                mic.loud,
                imuOk);
  if (imuOk) {
    Serial.printf(" ax=%.2f ay=%.2f az=%.2f gx=%.2f gy=%.2f gz=%.2f",
                  imu.ax,
                  imu.ay,
                  imu.az,
                  imu.gx,
                  imu.gy,
                  imu.gz);
  }
  Serial.println();
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);

  Serial.begin(115200);
  delay(500);

  pinMode(MIC_DIGITAL_PIN, INPUT_PULLUP);
  pinMode(MIC_ANALOG_PIN, INPUT);
  pinMode(5, INPUT_PULLUP);
  pinMode(37, INPUT);
  pinMode(38, INPUT);
  pinMode(39, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(MIC_ANALOG_PIN, ADC_11db);

  printPinout();
  setMode('q');
}

void loop() {
  M5.update();
  handleSerialInput();

  switch (activeMode) {
    case 'm':
      loopMic();
      break;
    case 'i':
      loopImu();
      break;
    case 'b':
      loopButtons();
      break;
    case 'a':
      loopAll();
      break;
    case 'q':
    default:
      delay(20);
      break;
  }
}
