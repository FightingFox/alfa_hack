"""Общий лёгковесный ML-каркас для моделей-детекторов ПД.

Каждая модель — бинарный классификатор: по тексту решает, содержит ли он
конкретный тип ПД. Признаки — хэшированные символьные n-граммы (1..3),
классификатор — логистическая регрессия, обучаемая стохастическим градиентным
спуском. Всё на чистом numpy: никаких тяжёлых зависимостей, веса — один .npz.

Модель максимально лёгкая: ~DIM весов (по умолчанию 512) + bias, обучение
занимает секунды на CPU, инференс — доли миллисекунды.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

# Размерность признакового вектора (число корзин хэша n-грамм).
DIM = 512
# Длина n-грамм, которые учитываются.
NGRAMS = (1, 2, 3)
# Число эпох обучения.
EPOCHS = 60
# Скорость обучения.
LR = 0.5
# L2-регуляризация.
L2 = 1e-4
# Порог классификации по умолчанию.
DEFAULT_THRESHOLD = 0.5


def _hash_ngram(ngram: str) -> int:
    """Стабильный хэш n-граммы в диапазон [0, DIM)."""
    return int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16) % DIM


def features(text: str, dim: int = DIM) -> np.ndarray:
    """Символьные n-граммы текста -> бинарный признаковый вектор (0/1).

    Каждая встреченная n-грамма помечает свою корзину хэша единицей.
    """
    vec = np.zeros(dim, dtype=np.float32)
    low = text.lower()
    for n in NGRAMS:
        for i in range(len(low) - n + 1):
            vec[_hash_ngram(low[i:i + n])] = 1.0
    return vec


def features_batch(texts: list[str], dim: int = DIM) -> np.ndarray:
    """Матрица признаков для списка текстов (N x DIM)."""
    return np.stack([features(t, dim) for t in texts])


class LogisticRegression:
    """Логистическая регрессия на numpy (бинарная)."""

    def __init__(self, dim: int = DIM):
        self.dim = dim
        self.w = np.zeros(dim, dtype=np.float32)
        self.b = 0.0

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Вероятность положительного класса для каждой строки X."""
        z = X @ self.w + self.b
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    def predict(self, X: np.ndarray, threshold: float = DEFAULT_THRESHOLD) -> np.ndarray:
        return (self.predict_proba(X) >= threshold).astype(np.int8)

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = EPOCHS, lr: float = LR, l2: float = L2) -> list[float]:
        """Обучить SGD-ом. Возвращает историю loss по эпохам."""
        n = X.shape[0]
        y = y.astype(np.float32)
        history: list[float] = []
        for _ in range(epochs):
            # Перемешиваем порядок примеров.
            perm = np.random.permutation(n)
            for i in perm:
                xi = X[i]
                p = self.predict_proba(xi[None, :])[0]
                err = p - y[i]
                grad_w = err * xi + l2 * self.w
                grad_b = err
                self.w -= lr * grad_w
                self.b -= lr * grad_b
            # Loss на эпоху (log-loss + L2).
            p = self.predict_proba(X)
            eps = 1e-9
            loss = -np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
            loss += 0.5 * l2 * float(np.dot(self.w, self.w))
            history.append(float(loss))
        return history

    def save(self, path: Path) -> None:
        np.savez_compressed(path, w=self.w, b=np.float32(self.b), dim=np.int32(self.dim))

    @classmethod
    def load(cls, path: Path) -> "LogisticRegression":
        data = np.load(path)
        m = cls(int(data["dim"]))
        m.w = data["w"].astype(np.float32)
        m.b = float(data["b"])
        return m


class PiiDetector:
    """Готовый детектор одного типа ПД: признаки + модель + метаданные.

    Инкапсулирует обучение, сохранение и инференс. Каждый тип ПД использует
    свой экземпляр, обученный на своей синтетике.
    """

    def __init__(self, code: str, name: str, dim: int = DIM, threshold: float = DEFAULT_THRESHOLD):
        self.code = code
        self.name = name
        self.dim = dim
        self.threshold = threshold
        self.model = LogisticRegression(dim)

    def fit(self, texts: list[str], labels: list[int], epochs: int = EPOCHS) -> list[float]:
        X = features_batch(texts, self.dim)
        y = np.asarray(labels, dtype=np.int8)
        return self.model.fit(X, y, epochs=epochs)

    def score(self, text: str) -> float:
        """Вероятность того, что текст содержит этот тип ПД."""
        return float(self.model.predict_proba(features(text, self.dim)[None, :])[0])

    def detect(self, text: str) -> bool:
        return self.score(text) >= self.threshold

    def save(self, folder: Path) -> None:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.model.save(folder / "model.npz")
        meta = {
            "code": self.code,
            "name": self.name,
            "dim": self.dim,
            "threshold": self.threshold,
        }
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, folder: Path) -> "PiiDetector":
        folder = Path(folder)
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        m = cls(meta["code"], meta["name"], dim=meta["dim"], threshold=meta["threshold"])
        m.model = LogisticRegression.load(folder / "model.npz")
        return m