#include <M5Unified.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <BMI088.h>

#define I2C_SDA 21
#define I2C_SCL 22

#define MIC_ANALOG_PIN 36
#define MIC_DIGITAL_PIN 26

const char* WIFI_SSID = "omnitest";
const char* WIFI_PASS = "omniband";

const char* MQTT_BROKER = "broker.hivemq.com";
const int   MQTT_PORT   = 1883;

const char* MQTT_CLIENT_ID = "omniband-coreink-01";
const char* TOPIC_RAW      = "omniband/sensor/raw";
const char* TOPIC_STATUS   = "omniband/device/status";
const char* TOPIC_ACTION   = "omniband/action";

WiFiClient espClient;
PubSubClient mqttClient(espClient);

Bmi088Accel accel(Wire, 0x19);
Bmi088Gyro gyro(Wire, 0x69);

bool imuOK = false;
unsigned long lastPublish = 0;
const unsigned long PUBLISH_INTERVAL_MS = 1000;

void drawLine(const String& line1, const String& line2 = "", const String& line3 = "") {
  M5.Display.clear();
  M5.Display.setTextSize(2);
  M5.Display.setCursor(10, 20);
  M5.Display.println(line1);
  if (line2.length()) {
    M5.Display.setCursor(10, 60);
    M5.Display.println(line2);
  }
  if (line3.length()) {
    M5.Display.setCursor(10, 100);
    M5.Display.println(line3);
  }
}

void connectWiFi() {
  drawLine("A ligar WiFi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    tries++;
    if (tries % 4 == 0) {
      drawLine("A ligar WiFi...", String("Tentativa: ") + tries);
    }
  }

  drawLine("WiFi OK", WiFi.localIP().toString());
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.print("MQTT RX [");
  Serial.print(topic);
  Serial.print("] ");
  Serial.println(message);

  String topicStr = String(topic);

  if (topicStr == TOPIC_ACTION) {
    if (message == "buzz") {
      M5.Speaker.tone(1000, 200);
      drawLine("Acao recebida", "buzz");
    } else if (message.startsWith("display:")) {
      String txt = message.substring(8);
      drawLine("Acao recebida", txt);
    } else {
      drawLine("Acao recebida", message);
    }
  }
}

void connectMQTT() {
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  while (!mqttClient.connected()) {
    drawLine("A ligar MQTT...");
    if (mqttClient.connect(MQTT_CLIENT_ID)) {
      mqttClient.subscribe(TOPIC_ACTION);
      mqttClient.publish(TOPIC_STATUS, "{\"status\":\"online\"}");
      drawLine("MQTT OK", TOPIC_ACTION);
    } else {
      delay(1000);
    }
  }
}

bool initIMU() {
  Wire.begin(I2C_SDA, I2C_SCL);

  int accelStatus = accel.begin();
  int gyroStatus  = gyro.begin();

  Serial.print("Accel status: ");
  Serial.println(accelStatus);
  Serial.print("Gyro status: ");
  Serial.println(gyroStatus);

  return (accelStatus >= 0 && gyroStatus >= 0);
}

void publishSensorPacket() {
  float ax = 0, ay = 0, az = 0;
  float gx = 0, gy = 0, gz = 0;

  if (imuOK) {
    accel.readSensor();
    gyro.readSensor();

    ax = accel.getAccelX_mss();
    ay = accel.getAccelY_mss();
    az = accel.getAccelZ_mss();

    gx = gyro.getGyroX_rads();
    gy = gyro.getGyroY_rads();
    gz = gyro.getGyroZ_rads();
  }

  int micAnalog = analogRead(MIC_ANALOG_PIN);
  int micDigital = digitalRead(MIC_DIGITAL_PIN);

  unsigned long ts = millis();

  String payload = "{";
  payload += "\"device\":\"omniband-coreink-01\",";
  payload += "\"ts\":" + String(ts) + ",";
  payload += "\"imu_ok\":" + String(imuOK ? "true" : "false") + ",";
  payload += "\"mic\":{";
  payload += "\"analog\":" + String(micAnalog) + ",";
  payload += "\"digital\":" + String(micDigital);
  payload += "},";
  payload += "\"imu\":{";
  payload += "\"ax\":" + String(ax, 3) + ",";
  payload += "\"ay\":" + String(ay, 3) + ",";
  payload += "\"az\":" + String(az, 3) + ",";
  payload += "\"gx\":" + String(gx, 3) + ",";
  payload += "\"gy\":" + String(gy, 3) + ",";
  payload += "\"gz\":" + String(gz, 3);
  payload += "}";
  payload += "}";

  Serial.println(payload);

  mqttClient.publish(TOPIC_RAW, payload.c_str());

  drawLine(
    "Pub MQTT OK",
    String("MIC A: ") + micAnalog + " D: " + micDigital,
    String("AX: ") + String(ax, 1) + " AY: " + String(ay, 1)
  );
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);

  Serial.begin(115200);
  delay(500);

  pinMode(MIC_ANALOG_PIN, INPUT);
  pinMode(MIC_DIGITAL_PIN, INPUT);

  drawLine("OMNIBAND", "Boot...");

  imuOK = initIMU();
  if (imuOK) {
    Serial.println("BMI088 OK");
  } else {
    Serial.println("BMI088 FAIL");
  }

  connectWiFi();
  connectMQTT();
}

void loop() {
  M5.update();

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  if (!mqttClient.connected()) {
    connectMQTT();
  }

  mqttClient.loop();

  if (millis() - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = millis();
    publishSensorPacket();
  }

  delay(10);
}
