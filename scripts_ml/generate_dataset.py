"""
OmniBand - Gerador de Dataset Sintético para IMU
==================================================
Gera dados de treino para 5 gestos + idle, simulando leituras
do BMI088 a 100 Hz durante 2 segundos (200 amostras).
"""

import numpy as np
import pandas as pd
import os

# Semente para reprodutibilidade
np.random.seed(42)

GESTURES = {
    0: "idle",
    1: "on",       # rodar pulso para cima (gz positivo)
    2: "off",      # rodar pulso para baixo (gz negativo)
    3: "dim_up",   # rodar para direita (gy positivo)
    4: "dim_down", # rodar para esquerda (gy negativo)
    5: "toggle",   # agitar / toque (alta energia em todos os eixos)
}

GESTURE_LABEL = {v: k for k, v in GESTURES.items()}

SAMPLES_PER_GESTURE = 80
SAMPLE_RATE = 100       # Hz
WINDOW_MS = 2000        # 2 segundos
SAMPLES_PER_WINDOW = SAMPLE_RATE * WINDOW_MS // 1000  # 200

# Ruído de base do sensor (valores típicos BMI088)
ACCEL_NOISE_STD = 0.05
GYRO_NOISE_STD = 0.3


def generate_idle(n=SAMPLES_PER_GESTURE):
    """Ruído de fundo - utilizador parado."""
    data = []
    for _ in range(n):
        ax = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        ay = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        az = np.random.normal(9.8, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)  # gravidade
        gx = np.random.normal(0, GYRO_NOISE_STD, SAMPLES_PER_WINDOW)
        gy = np.random.normal(0, GYRO_NOISE_STD, SAMPLES_PER_WINDOW)
        gz = np.random.normal(0, GYRO_NOISE_STD, SAMPLES_PER_WINDOW)
        data.append(np.column_stack([ax, ay, az, gx, gy, gz]))
    return np.array(data)


def add_noise(signal, noise_std=GYRO_NOISE_STD):
    return signal + np.random.normal(0, noise_std, signal.shape)


def generate_gesture_on(n=SAMPLES_PER_GESTURE):
    """Gesto: rodar pulso para cima → gz positivo forte no meio."""
    data = []
    mid = SAMPLES_PER_WINDOW // 2
    for _ in range(n):
        ax = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        ay = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        az = np.random.normal(9.8, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)

        # Pulso gaussiano positivo em gz
        pulse = np.exp(-0.5 * ((np.arange(SAMPLES_PER_WINDOW) - mid) / 12) ** 2)
        gz = add_noise(pulse * 300, 0.4)
        gx = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)
        gy = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)

        data.append(np.column_stack([ax, ay, az, gx, gy, gz]))
    return np.array(data)


def generate_gesture_off(n=SAMPLES_PER_GESTURE):
    """Gesto: rodar pulso para baixo → gz negativo forte no meio."""
    data = []
    mid = SAMPLES_PER_WINDOW // 2
    for _ in range(n):
        ax = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        ay = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        az = np.random.normal(9.8, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)

        pulse = np.exp(-0.5 * ((np.arange(SAMPLES_PER_WINDOW) - mid) / 12) ** 2)
        gz = add_noise(-pulse * 300, 0.4)
        gx = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)
        gy = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)

        data.append(np.column_stack([ax, ay, az, gx, gy, gz]))
    return np.array(data)


def generate_gesture_dim_up(n=SAMPLES_PER_GESTURE):
    """Gesto: rodar pulso direita → gy positivo."""
    data = []
    mid = SAMPLES_PER_WINDOW // 2
    for _ in range(n):
        ax = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        ay = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        az = np.random.normal(9.8, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)

        pulse = np.exp(-0.5 * ((np.arange(SAMPLES_PER_WINDOW) - mid) / 14) ** 2)
        gy = add_noise(pulse * 250, 0.4)
        gx = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)
        gz = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)

        data.append(np.column_stack([ax, ay, az, gx, gy, gz]))
    return np.array(data)


def generate_gesture_dim_down(n=SAMPLES_PER_GESTURE):
    """Gesto: rodar pulso esquerda → gy negativo."""
    data = []
    mid = SAMPLES_PER_WINDOW // 2
    for _ in range(n):
        ax = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        ay = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        az = np.random.normal(9.8, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)

        pulse = np.exp(-0.5 * ((np.arange(SAMPLES_PER_WINDOW) - mid) / 14) ** 2)
        gy = add_noise(-pulse * 250, 0.4)
        gx = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)
        gz = np.random.normal(0, 0.4, SAMPLES_PER_WINDOW)

        data.append(np.column_stack([ax, ay, az, gx, gy, gz]))
    return np.array(data)


def generate_gesture_toggle(n=SAMPLES_PER_GESTURE):
    """Gesto: agitar → oscilações rápidas em todos os giroscópios."""
    data = []
    for _ in range(n):
        ax = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        ay = np.random.normal(0, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)
        az = np.random.normal(9.8, ACCEL_NOISE_STD, SAMPLES_PER_WINDOW)

        # Oscilação rápida em todos os eixos
        t = np.arange(SAMPLES_PER_WINDOW)
        gx = np.sin(t * 0.5) * 150 + np.random.normal(0, 0.5, SAMPLES_PER_WINDOW)
        gy = np.cos(t * 0.5 + 0.5) * 120 + np.random.normal(0, 0.5, SAMPLES_PER_WINDOW)
        gz = np.sin(t * 0.5 + 1.0) * 180 + np.random.normal(0, 0.5, SAMPLES_PER_WINDOW)

        data.append(np.column_stack([ax, ay, az, gx, gy, gz]))
    return np.array(data)


def compute_features(sample):
    """
    Extrai features de uma janela de 200x6.
    Similar ao que o Edge Impulse faz no bloco "Spectral Features".
    """
    n = len(sample)
    features = []

    for channel_idx in range(6):
        channel = sample[:, channel_idx]
        # Estatísticas no tempo
        features.append(np.mean(channel))
        features.append(np.std(channel))
        features.append(np.max(channel))
        features.append(np.min(channel))
        features.append(np.max(channel) - np.min(channel))  # peak-to-peak
        features.append(np.sqrt(np.mean(channel ** 2)))     # RMS

        # Energia (sum of squares)
        features.append(np.sum(channel ** 2) / n)

        # Frequência: valores absolutos da FFT nos primeiros bins
        fft_vals = np.abs(np.fft.rfft(channel))
        fft_vals = fft_vals[1:6]  # primeiros 5 bins (excluindo DC)
        features.extend(fft_vals)

    return np.array(features)


def generate_dataset():
    """Gera dataset completo com features."""
    print("=" * 60)
    print("OmniBand - Gerador de Dataset Sintético para IMU")
    print("=" * 60)

    generators = {
        0: generate_idle,
        1: generate_gesture_on,
        2: generate_gesture_off,
        3: generate_gesture_dim_up,
        4: generate_gesture_dim_down,
        5: generate_gesture_toggle,
    }

    all_X = []
    all_y = []

    total_samples = 0
    for label, gen in generators.items():
        raw = gen()
        n = raw.shape[0]
        print(f"  Gerando {n} amostras para '{GESTURES[label]}'...")

        for i in range(n):
            feats = compute_features(raw[i])
            all_X.append(feats)
            all_y.append(label)

        total_samples += n

    X = np.array(all_X)
    y = np.array(all_y)

    print(f"\n  Total: {total_samples} amostras, {X.shape[1]} features cada")
    return X, y


def save_dataset(X, y, path="scripts_ml/gestos_dataset"):
    """Guarda dataset em CSV."""
    os.makedirs(path, exist_ok=True)

    # Nomes das colunas de features
    channel_names = ["ax", "ay", "az", "gx", "gy", "gz"]
    feature_names = []
    for ch in channel_names:
        feature_names.extend([
            f"{ch}_mean", f"{ch}_std", f"{ch}_max", f"{ch}_min",
            f"{ch}_p2p", f"{ch}_rms", f"{ch}_energy",
            f"{ch}_fft1", f"{ch}_fft2", f"{ch}_fft3", f"{ch}_fft4", f"{ch}_fft5",
        ])

    cols = feature_names + ["label"]
    df = pd.DataFrame(np.column_stack([X, y]), columns=cols)
    df["label"] = df["label"].astype(int)

    # Split treino (80%) / teste (20%)
    from sklearn.model_selection import train_test_split
    train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df["label"])

    train_path = os.path.join(path, "imu_train.csv")
    test_path = os.path.join(path, "imu_test.csv")

    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    print(f"\n  Dataset guardado em: {path}/")
    print(f"    Treino: {len(train_df)} amostras → imu_train.csv")
    print(f"    Teste:  {len(test_df)} amostras → imu_test.csv")

    return train_df, test_df


if __name__ == "__main__":
    X, y = generate_dataset()
    save_dataset(X, y)
    print("  ✅ Dataset gerado com sucesso!")