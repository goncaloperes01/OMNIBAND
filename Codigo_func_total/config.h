#pragma once

// Edita estes valores antes de carregar para o M5Stack CoreInk.
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#define HUB_EVENT_URL "http://192.168.1.50:8080/api/event"

#define DEVICE_ID "omniband-coreink-01"
#define DEFAULT_ROOM "corredor"

// CoreInk + U096 ligado por breakout/proto base:
// U096 amarelo -> GPIO26 (digital), branco -> GPIO36 (analogico/ADC1).
#define MIC_DIGITAL_PIN 26
#define MIC_ANALOG_PIN 36

// CoreInk HY2.0-4P externo para o BMI088.
// O firmware testa automaticamente as duas orientacoes mais comuns.
#define I2C_PRIMARY_SDA 33
#define I2C_PRIMARY_SCL 32
#define I2C_FALLBACK_SDA 32
#define I2C_FALLBACK_SCL 33

// Afinacao rapida para a demonstracao.
#define AUDIO_PULSE_THRESHOLD 650
#define WAKE_GYRO_THRESHOLD 220.0f
#define WAKE_ACCEL_DELTA_THRESHOLD 420.0f
#define GESTURE_GYRO_THRESHOLD 170.0f
