#pragma once

// ════════════════════════════════════════════════════════════
//  Configuração do OmniBand
//  Edita antes de carregar para o M5Stack CoreInk.
// ════════════════════════════════════════════════════════════

// ─── TinyML ──────────────────────────────────────────────
// Ativa o modelo de ML treinado para classificação de gestos.
// Descomenta para usar o modelo treinado (gesture_model.h).
// Comentado = usa thresholds manuais (comportamento original).
#define USE_ML_MODEL 1

// ─── Wi-Fi ───────────────────────────────────────────────
#define WIFI_SSID ""
#define WIFI_PASSWORD ""
#define HUB_EVENT_URL "http://192.168.1.50:8080/api/event"

#define DEVICE_ID "omniband-coreink-01"
#define DEFAULT_ROOM "corredor"

// ─── Microfone U096 ──────────────────────────────────────
// CoreInk + U096: amarelo -> GPIO26 (digital), branco -> GPIO36 (ADC1)
#define MIC_DIGITAL_PIN 26
#define MIC_ANALOG_PIN 36

// ─── BMI088 (IMU) ────────────────────────────────────────
// CoreInk HY2.0-4P externo. O firmware testa ambas as orientações.
#define I2C_PRIMARY_SDA 33
#define I2C_PRIMARY_SCL 32
#define I2C_FALLBACK_SDA 32
#define I2C_FALLBACK_SCL 33

// ─── Thresholds ──────────────────────────────────────────
// Usados para raise-to-wake e como fallback da classificação ML.
#define AUDIO_PULSE_THRESHOLD 650
#define WAKE_GYRO_THRESHOLD 220.0f
#define WAKE_ACCEL_DELTA_THRESHOLD 420.0f
#define GESTURE_GYRO_THRESHOLD 170.0f
