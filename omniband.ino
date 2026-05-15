#include <M5Unified.h>
#include <Wire.h>
#include "BMI088.h"

#define MIC_DIGITAL_PIN 26
#define MIC_ANALOG_PIN  36

BMI088 bmi088(BMI088_ACC_ADDRESS, BMI088_GYRO_ADDRESS);

bool modoMicrofone = true;
bool imuOK = false;
unsigned long lastUpdate = 0;

void mostrarModo() {
  M5.Display.clear();
  M5.Display.setTextSize(2);
  M5.Display.setCursor(10, 15);

  if (modoMicrofone) {
    M5.Display.print("Modo: MIC");
    M5.Display.setCursor(10, 45);
    M5.Display.print("Botao cima troca");
  } else {
    M5.Display.print("Modo: IMU");
    M5.Display.setCursor(10, 45);
    M5.Display.print("Botao cima troca");
  }
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);

  Serial.begin(115200);

  pinMode(MIC_DIGITAL_PIN, INPUT);
  pinMode(MIC_ANALOG_PIN, INPUT);

  Wire.begin(21, 22);

  if (bmi088.isConnection()) {
    bmi088.initialize();
    imuOK = true;
    Serial.println("BMI088 ligado");
  } else {
    imuOK = false;
    Serial.println("BMI088 nao encontrado");
  }

  mostrarModo();
}

void loop() {
  M5.update();

  if (M5.BtnEXT.wasPressed()) {
    modoMicrofone = !modoMicrofone;
    mostrarModo();
    delay(200);
  }

  if (millis() - lastUpdate > 1000) {
    lastUpdate = millis();

    if (modoMicrofone) {
      int micDigital = digitalRead(MIC_DIGITAL_PIN);
      int micAnalog = analogRead(MIC_ANALOG_PIN);

      Serial.print("MIC -> Digital: ");
      Serial.print(micDigital);
      Serial.print(" | Analog: ");
      Serial.println(micAnalog);

      M5.Display.clear();
      M5.Display.setTextSize(2);
      M5.Display.setCursor(10, 15);
      M5.Display.print("Modo: MIC");

      M5.Display.setCursor(10, 55);
      M5.Display.printf("D: %d", micDigital);

      M5.Display.setCursor(10, 90);
      M5.Display.printf("A: %d", micAnalog);

      M5.Display.setCursor(10, 145);
      M5.Display.print("Botao cima troca");
    }
    else {
      M5.Display.clear();
      M5.Display.setTextSize(2);
      M5.Display.setCursor(10, 15);
      M5.Display.print("Modo: IMU");

      if (!imuOK) {
        M5.Display.setCursor(10, 60);
        M5.Display.print("IMU nao ligado");
      } else {
        float ax = 0, ay = 0, az = 0;
        float gx = 0, gy = 0, gz = 0;

        bmi088.getAcceleration(&ax, &ay, &az);
        bmi088.getGyroscope(&gx, &gy, &gz);

        Serial.print("IMU -> AX: ");
        Serial.print(ax);
        Serial.print(" AY: ");
        Serial.print(ay);
        Serial.print(" AZ: ");
        Serial.println(az);

        M5.Display.setCursor(10, 45);
        M5.Display.printf("AX: %.1f", ax);

        M5.Display.setCursor(10, 75);
        M5.Display.printf("AY: %.1f", ay);

        M5.Display.setCursor(10, 105);
        M5.Display.printf("AZ: %.1f", az);

        M5.Display.setCursor(10, 145);
        M5.Display.print("Botao cima troca");
      }
    }
  }

  delay(10);
}