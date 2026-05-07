"""Aim-delta regression helpers for the MuJoCo rubber band launcher."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

BASE_FEATURE_NAMES = [
    "norm_err_x",
    "norm_err_y",
    "bbox_w_norm",
    "bbox_h_norm",
    "bbox_area_norm",
    "bbox_conf",
    "current_yaw_rad",
    "current_pitch_rad",
]

TARGET_NAMES = ["delta_yaw_rad", "delta_pitch_rad"]


def build_poly_feature_names(base_names=BASE_FEATURE_NAMES):
    names = list(base_names)
    names.extend(f"{name}^2" for name in base_names)
    for i, left in enumerate(base_names):
        for right in base_names[i + 1:]:
            names.append(f"{left}*{right}")
    return names


FEATURE_NAMES = build_poly_feature_names()


def expand_features(base_features):
    x = np.asarray(base_features, dtype=np.float64)
    if x.ndim == 1:
        x = x.reshape(1, -1)

    parts = [x, x * x]
    interactions = []
    for i in range(x.shape[1]):
        for j in range(i + 1, x.shape[1]):
            interactions.append((x[:, i] * x[:, j]).reshape(-1, 1))
    if interactions:
        parts.append(np.hstack(interactions))
    return np.hstack(parts)


def detection_to_base_features(detection, current_yaw_rad, current_pitch_rad):
    x1, y1, x2, y2 = detection["box"]
    bbox_w = x2 - x1
    bbox_h = y2 - y1
    bbox_cx = (x1 + x2) / 2
    bbox_cy = (y1 + y2) / 2
    err_x = bbox_cx - CAMERA_WIDTH / 2
    err_y = bbox_cy - CAMERA_HEIGHT / 2

    return np.array([
        err_x / (CAMERA_WIDTH / 2),
        err_y / (CAMERA_HEIGHT / 2),
        bbox_w / CAMERA_WIDTH,
        bbox_h / CAMERA_HEIGHT,
        (bbox_w * bbox_h) / (CAMERA_WIDTH * CAMERA_HEIGHT),
        float(detection.get("conf", 0.0)),
        current_yaw_rad,
        current_pitch_rad,
    ], dtype=np.float64)


def fit_ridge(x, y, alpha):
    x_aug = np.column_stack([np.ones(len(x)), x])
    penalty = np.eye(x_aug.shape[1], dtype=np.float64) * alpha
    penalty[0, 0] = 0.0
    return np.linalg.solve(x_aug.T @ x_aug + penalty, x_aug.T @ y)


def predict_with_weights(x, weights):
    x_aug = np.column_stack([np.ones(len(x)), x])
    return x_aug @ weights


@dataclass
class AimDeltaModel:
    weights: np.ndarray
    mean: np.ndarray
    std: np.ndarray
    alpha: float
    metadata: dict

    @classmethod
    def load(cls, path):
        data = np.load(path, allow_pickle=False)
        metadata = json.loads(str(data["metadata"]))
        return cls(
            weights=data["weights"],
            mean=data["mean"],
            std=data["std"],
            alpha=float(data["alpha"]),
            metadata=metadata,
        )

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            path,
            weights=self.weights,
            mean=self.mean,
            std=self.std,
            alpha=np.array(self.alpha, dtype=np.float64),
            feature_names=np.array(FEATURE_NAMES),
            base_feature_names=np.array(BASE_FEATURE_NAMES),
            target_names=np.array(TARGET_NAMES),
            metadata=json.dumps(self.metadata, ensure_ascii=False),
        )

    def predict_base(self, base_features):
        poly = expand_features(base_features)
        x = (poly - self.mean) / self.std
        return predict_with_weights(x, self.weights)

    def predict_detection(self, detection, current_yaw_rad, current_pitch_rad):
        base = detection_to_base_features(detection, current_yaw_rad, current_pitch_rad)
        return self.predict_base(base)[0]
