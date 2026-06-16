"""
OmniBand - Treino de Modelo TinyML para Arduino
=================================================
Treina uma rede neuronal leve (2 camadas densas) para classificar
gestos IMU. Exporta para C++ header (gesture_model.h) sem
dependências de TensorFlow Lite.

O modelo usa features estatísticas + frequência (72 features) e
classifica em 6 classes (idle, on, off, dim_up, dim_down, toggle).
"""

import numpy as np
import pandas as pd
import os
import sys

# ─── Config ───────────────────────────────────────────────
FEATURE_FILE = os.path.join("scripts_ml", "gestos_dataset", "imu_train.csv")
TEST_FILE = os.path.join("scripts_ml", "gestos_dataset", "imu_test.csv")
OUTPUT_HEADER = os.path.join("Codigo_func_total", "gesture_model.h")

# Hiperparâmetros (ajustados para ESP32)
HIDDEN_SIZE = 32
LEARNING_RATE = 0.01
EPOCHS = 200
BATCH_SIZE = 16

# Labels
GESTURE_NAMES = ["idle", "on", "off", "dim_up", "dim_down", "toggle"]

# ─── Seed ──────────────────────────────────────────────────
np.random.seed(42)


def load_dataset(path):
    """Load CSV dataset, returns X (samples x features) and y (labels)."""
    if not os.path.isfile(path):
        print(f"[ERRO] Ficheiro não encontrado: {path}")
        print("  Gera primeiro o dataset: python scripts_ml/generate_dataset.py")
        sys.exit(1)

    df = pd.read_csv(path)
    y = df["label"].values.astype(int)
    X = df.drop(columns=["label"]).values.astype(np.float32)
    print(f"  Dataset: {X.shape[0]} amostras, {X.shape[1]} features")
    return X, y


def standardize(X_train, X_test=None):
    """Z-score normalization."""
    mean = np.mean(X_train, axis=0, keepdims=True)
    std = np.std(X_train, axis=0, keepdims=True) + 1e-8
    X_train_norm = (X_train - mean) / std
    X_test_norm = (X_test - mean) / std if X_test is not None else None
    return X_train_norm, X_test_norm, mean.flatten(), std.flatten()


def one_hot(y, num_classes=6):
    return np.eye(num_classes)[y]


def relu(x):
    return np.maximum(0, x)


def softmax(x):
    ex = np.exp(x - np.max(x, axis=1, keepdims=True))
    return ex / np.sum(ex, axis=1, keepdims=True)


def cross_entropy_loss(y_pred, y_true):
    n = y_true.shape[0]
    eps = 1e-8
    loss = -np.sum(y_true * np.log(y_pred + eps)) / n
    return loss


def accuracy(y_pred, y_true):
    return np.mean(np.argmax(y_pred, axis=1) == np.argmax(y_true, axis=1))


# ─── Model: 2-layer neural network ─────────────────────────
class TinyMLP:
    """2-layer MLP: input → hidden (ReLU) → output (softmax)."""

    def __init__(self, input_size, hidden_size, output_size, lr=0.01):
        self.lr = lr
        # He init para ReLU
        self.W1 = np.random.randn(input_size, hidden_size) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, hidden_size))
        self.W2 = np.random.randn(hidden_size, output_size) * np.sqrt(2.0 / hidden_size)
        self.b2 = np.zeros((1, output_size))

    def forward(self, X):
        self.z1 = X @ self.W1 + self.b1
        self.a1 = relu(self.z1)
        self.z2 = self.a1 @ self.W2 + self.b2
        self.a2 = softmax(self.z2)
        return self.a2

    def backward(self, X, y_true):
        n = X.shape[0]

        # Output layer
        dz2 = self.a2 - y_true
        dW2 = self.a1.T @ dz2 / n
        db2 = np.sum(dz2, axis=0, keepdims=True) / n

        # Hidden layer
        da1 = dz2 @ self.W2.T
        dz1 = da1 * (self.z1 > 0)  # ReLU derivative
        dW1 = X.T @ dz1 / n
        db1 = np.sum(dz1, axis=0, keepdims=True) / n

        # Gradient descent
        self.W2 -= self.lr * dW2
        self.b2 -= self.lr * db2
        self.W1 -= self.lr * dW1
        self.b1 -= self.lr * db1

    def predict(self, X):
        return self.forward(X)

    def predict_class(self, X):
        return np.argmax(self.predict(X), axis=1)


def export_to_c_header(model, mean, std, feature_labels, filename):
    """
    Exporta os pesos treinados para um header C++ que pode ser
    incluído diretamente no firmware Arduino, sem dependências.
    """
    print(f"\n  A exportar modelo para: {filename}")

    n_classes = len(GESTURE_NAMES)
    n_features = len(feature_labels)

    # Formata arrays para C++
    def format_array(name, arr, indent="  "):
        """Formata array numpy 2D para inicializador C++ estático."""
        lines = []
        if arr.ndim == 1:
            vals = ", ".join(f"{v:.8f}f" for v in arr.flatten())
            lines.append(f"{indent}static const float {name}[{arr.shape[0]}] = {{{vals}}};")
        else:
            lines.append(f"{indent}static const float {name}[{arr.shape[0]}][{arr.shape[1]}] = {{")
            for row in arr:
                vals = ", ".join(f"{v:.8f}f" for v in row)
                lines.append(f"{indent}  {{{vals}}},")
            lines.append(f"{indent}}};")
        return "\n".join(lines)

    header = f"""// ============================================================
// OmniBand - Gesture Recognition Model (TinyML)
// Modelo: MLP 2 camadas
// Features: {n_features} (estatísticas + frequência)
// Classes: {n_classes} ({', '.join(GESTURE_NAMES)})
// Gerado automaticamente por train_model.py
// ============================================================
#ifndef GESTURE_MODEL_H
#define GESTURE_MODEL_H

#include <stdint.h>
#include <math.h>

// ─── Constantes do modelo ────────────────────────────────
#define GESTURE_MODEL_N_FEATURES {n_features}
#define GESTURE_MODEL_HIDDEN_SIZE {model.W1.shape[1]}
#define GESTURE_MODEL_N_CLASSES {n_classes}

// ─── Normalização (Z-score) ──────────────────────────────
{format_array("MODEL_MEAN", mean)}
{format_array("MODEL_STD", std)}

// ─── Pesos da camada oculta (input → hidden) ─────────────
{format_array("MODEL_W1", model.W1)}
{format_array("MODEL_B1", model.b1)}

// ─── Pesos da camada de saída (hidden → output) ──────────
{format_array("MODEL_W2", model.W2)}
{format_array("MODEL_B2", model.b2)}

// ─── Nomes dos gestos ─────────────────────────────────────
static const char* MODEL_GESTURE_NAMES[{n_classes}] = {{{", ".join(f'"{n}"' for n in GESTURE_NAMES)}}};

// ─── Função de inferência ─────────────────────────────────
static inline int gesture_model_predict(const float features[GESTURE_MODEL_N_FEATURES]) {{
    float z1[GESTURE_MODEL_HIDDEN_SIZE];
    float a1[GESTURE_MODEL_HIDDEN_SIZE];
    float z2[GESTURE_MODEL_N_CLASSES];
    float a2[GESTURE_MODEL_N_CLASSES];

    // Normalizar input
    float norm[GESTURE_MODEL_N_FEATURES];
    for (int i = 0; i < GESTURE_MODEL_N_FEATURES; i++) {{
        norm[i] = (features[i] - MODEL_MEAN[i]) / MODEL_STD[i];
    }}

    // Camada oculta: z1 = norm @ W1 + b1 → ReLU
    for (int j = 0; j < GESTURE_MODEL_HIDDEN_SIZE; j++) {{
        z1[j] = MODEL_B1[0][j];
        for (int i = 0; i < GESTURE_MODEL_N_FEATURES; i++) {{
            z1[j] += norm[i] * MODEL_W1[i][j];
        }}
        a1[j] = z1[j] > 0 ? z1[j] : 0;  // ReLU
    }}

    // Camada de saída: z2 = a1 @ W2 + b2 → softmax
    float max_val = -1e10f;
    for (int k = 0; k < GESTURE_MODEL_N_CLASSES; k++) {{
        z2[k] = MODEL_B2[0][k];
        for (int j = 0; j < GESTURE_MODEL_HIDDEN_SIZE; j++) {{
            z2[k] += a1[j] * MODEL_W2[j][k];
        }}
        if (z2[k] > max_val) max_val = z2[k];
    }}

    // Softmax
    float sum_exp = 0;
    for (int k = 0; k < GESTURE_MODEL_N_CLASSES; k++) {{
        a2[k] = expf(z2[k] - max_val);
        sum_exp += a2[k];
    }}
    for (int k = 0; k < GESTURE_MODEL_N_CLASSES; k++) {{
        a2[k] /= sum_exp;
    }}

    // Classe com maior probabilidade
    int best = 0;
    float best_prob = a2[0];
    for (int k = 1; k < GESTURE_MODEL_N_CLASSES; k++) {{
        if (a2[k] > best_prob) {{
            best_prob = a2[k];
            best = k;
        }}
    }}

    return best;
}}

#endif // GESTURE_MODEL_H
"""
    with open(filename, "w") as f:
        f.write(header)
    print(f"  ✅ Ficheiro gerado: {filename}")


def main():
    print("=" * 60)
    print("  OmniBand - Treino de Modelo TinyML")
    print("=" * 60)

    # 1. Carregar dados
    print("\n[1/5] A carregar datasets...")
    X_train, y_train = load_dataset(FEATURE_FILE)
    X_test, y_test = load_dataset(TEST_FILE)

    # 2. Normalizar
    print("\n[2/5] A normalizar dados (Z-score)...")
    X_train_norm, X_test_norm, mean, std = standardize(X_train, X_test)

    # 3. Converter para one-hot
    print("\n[3/5] A preparar labels...")
    y_train_oh = one_hot(y_train, len(GESTURE_NAMES))
    y_test_oh = one_hot(y_test, len(GESTURE_NAMES))

    n_features = X_train.shape[1]

    # 4. Treinar
    print(f"\n[4/5] A treinar modelo ({EPOCHS} epochs)...")
    model = TinyMLP(n_features, HIDDEN_SIZE, len(GESTURE_NAMES), lr=LEARNING_RATE)

    best_test_acc = 0
    for epoch in range(1, EPOCHS + 1):
        # Forward + backward em mini-batches
        n = X_train_norm.shape[0]
        indices = np.random.permutation(n)
        X_shuffled = X_train_norm[indices]
        y_shuffled = y_train_oh[indices]

        for start in range(0, n, BATCH_SIZE):
            end = min(start + BATCH_SIZE, n)
            X_batch = X_shuffled[start:end]
            y_batch = y_shuffled[start:end]

            pred = model.forward(X_batch)
            model.backward(X_batch, y_batch)

        # Avaliação
        if epoch % 20 == 0 or epoch == 1 or epoch == EPOCHS:
            train_pred = model.predict(X_train_norm)
            test_pred = model.predict(X_test_norm)
            train_loss = cross_entropy_loss(train_pred, y_train_oh)
            test_loss = cross_entropy_loss(test_pred, y_test_oh)
            train_acc = accuracy(train_pred, y_train_oh)
            test_acc = accuracy(test_pred, y_test_oh)
            if test_acc > best_test_acc:
                best_test_acc = test_acc
            print(f"    Epoch {epoch:4d}: train_loss={train_loss:.4f} test_loss={test_loss:.4f} "
                  f"train_acc={train_acc:.4f} test_acc={test_acc:.4f}")

    # 5. Exportar
    print(f"\n[5/5] A exportar modelo para C++...")
    print(f"\n  📊 Resultados finais:")
    train_pred = model.predict(X_train_norm)
    test_pred = model.predict(X_test_norm)
    print(f"    Acurácia treino: {accuracy(train_pred, y_train_oh):.4f}")
    print(f"    Acurácia teste:  {accuracy(test_pred, y_test_oh):.4f}")
    print(f"    Melhor teste:    {best_test_acc:.4f}")

    # Nomes das colunas de features (para referência)
    channel_names = ["ax", "ay", "az", "gx", "gy", "gz"]
    feature_labels = []
    for ch in channel_names:
        feature_labels.extend([
            f"{ch}_mean", f"{ch}_std", f"{ch}_max", f"{ch}_min",
            f"{ch}_p2p", f"{ch}_rms", f"{ch}_energy",
            f"{ch}_fft1", f"{ch}_fft2", f"{ch}_fft3", f"{ch}_fft4", f"{ch}_fft5",
        ])

    export_to_c_header(model, mean, std, feature_labels, OUTPUT_HEADER)

    print("\n" + "=" * 60)
    print("  ✅ Modelo treinado e exportado com sucesso!")
    print(f"  📁 {OUTPUT_HEADER}")
    print(f"  🧠 Arquitetura: {n_features} → {HIDDEN_SIZE} → {len(GESTURE_NAMES)}")
    print(f"  📊 Acurácia teste: {accuracy(test_pred, y_test_oh):.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()