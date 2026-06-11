#pragma once

// Copia os mesmos valores do firmware principal quando quiseres testar WiFi/hub.
#define WIFI_SSID "CasaLt33"
#define WIFI_PASSWORD "luisdiogo"
#define HUB_EVENT_URL "http://192.168.1.50:8080/api/event"

// Ligacoes no M5Stack CoreInk:
// BMI088 no HY2.0-4P externo: branco=SDA=G33, amarelo=SCL=G32.
#define I2C_SDA_PIN 33
#define I2C_SCL_PIN 32
#define I2C_FALLBACK_SDA_PIN 32
#define I2C_FALLBACK_SCL_PIN 33

// U096 por breakout/proto base: amarelo=digital=G26, branco=analogico=G36.
#define MIC_DIGITAL_PIN 26
#define MIC_ANALOG_PIN 36
#define MIC_DIGITAL_ACTIVE_LOW 0

#define AUDIO_PULSE_THRESHOLD 650
