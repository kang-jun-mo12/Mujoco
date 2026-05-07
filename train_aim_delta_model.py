"""Train a ridge regression model that maps YOLO bbox features to aim deltas."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from aim_delta_model import (
    AimDeltaModel,
    BASE_FEATURE_NAMES,
    TARGET_NAMES,
    expand_features,
    fit_ridge,
    predict_with_weights,
)

DATASET_PATH = "datasets/aim_training_data_5cm.csv"
MODEL_PATH = "models/aim_delta_ridge_5cm.npz"
REPORT_PATH = "reports/aim_delta_model_5cm.md"
ALPHAS = [0.0, 1e-6, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0]


def load_numeric_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    data = {}
    names = set(BASE_FEATURE_NAMES + TARGET_NAMES + ["target_x", "target_y", "bbox_w", "bbox_h", "hit_success"])
    for name in names:
        data[name] = np.array([float(row[name]) for row in rows], dtype=np.float64)
    return data, len(rows)


def make_training_mask(data, min_conf, min_bbox_size):
    mask = np.ones(len(data["target_x"]), dtype=bool)
    for values in data.values():
        mask &= np.isfinite(values)
    mask &= data["hit_success"] == 1
    mask &= data["bbox_conf"] >= min_conf
    mask &= data["bbox_w"] >= min_bbox_size
    mask &= data["bbox_h"] >= min_bbox_size
    mask &= np.abs(np.rad2deg(data["delta_yaw_rad"])) <= 5
    mask &= np.abs(np.rad2deg(data["delta_pitch_rad"])) <= 4
    return mask


def build_matrices(data, mask):
    base = np.column_stack([data[name][mask] for name in BASE_FEATURE_NAMES])
    targets = np.column_stack([data[name][mask] for name in TARGET_NAMES])
    groups = np.column_stack([data["target_x"][mask], data["target_y"][mask]])
    return base, targets, groups


def group_split(groups, validation_ratio, seed):
    rounded = np.round(groups, 4)
    unique_groups = np.unique(rounded, axis=0)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(unique_groups))
    val_count = max(1, int(round(len(unique_groups) * validation_ratio)))
    val_groups = {tuple(unique_groups[i]) for i in order[:val_count]}
    val_mask = np.array([tuple(row) in val_groups for row in rounded], dtype=bool)
    return ~val_mask, val_mask, len(unique_groups)


def standardize(train_x, all_x):
    mean = train_x.mean(axis=0)
    std = train_x.std(axis=0)
    std[std < 1e-12] = 1.0
    return (all_x - mean) / std, mean, std


def metrics(y_true, y_pred):
    err = np.rad2deg(y_pred - y_true)
    rmse = np.sqrt(np.mean(err * err, axis=0))
    mae = np.mean(np.abs(err), axis=0)
    max_abs = np.max(np.abs(err), axis=0)
    ss_res = np.sum((y_true - y_pred) ** 2, axis=0)
    ss_tot = np.sum((y_true - y_true.mean(axis=0)) ** 2, axis=0)
    r2 = 1 - ss_res / ss_tot
    within_1deg = np.mean((np.abs(err[:, 0]) <= 1.0) & (np.abs(err[:, 1]) <= 1.0))
    within_05deg = np.mean((np.abs(err[:, 0]) <= 0.5) & (np.abs(err[:, 1]) <= 0.5))
    return {
        "rmse_yaw_deg": rmse[0],
        "rmse_pitch_deg": rmse[1],
        "mae_yaw_deg": mae[0],
        "mae_pitch_deg": mae[1],
        "max_abs_yaw_deg": max_abs[0],
        "max_abs_pitch_deg": max_abs[1],
        "r2_yaw": r2[0],
        "r2_pitch": r2[1],
        "within_1deg": within_1deg,
        "within_05deg": within_05deg,
    }


def train_and_evaluate(base, targets, groups, validation_ratio, seed):
    poly = expand_features(base)
    train_mask, val_mask, group_count = group_split(groups, validation_ratio, seed)
    train_x_raw = poly[train_mask]
    val_x_raw = poly[val_mask]
    train_y = targets[train_mask]
    val_y = targets[val_mask]

    train_x_all, mean, std = standardize(train_x_raw, poly)
    train_x = train_x_all[train_mask]
    val_x = train_x_all[val_mask]

    alpha_results = []
    best = None
    for alpha in ALPHAS:
        weights = fit_ridge(train_x, train_y, alpha)
        val_pred = predict_with_weights(val_x, weights)
        result = metrics(val_y, val_pred)
        result["alpha"] = alpha
        alpha_results.append(result)
        score = result["rmse_yaw_deg"] + result["rmse_pitch_deg"]
        if best is None or score < best[0]:
            best = (score, alpha, weights, result)

    best_alpha = best[1]
    _, final_mean, final_std = standardize(poly, poly)
    final_x = (poly - final_mean) / final_std
    final_weights = fit_ridge(final_x, targets, best_alpha)

    final_pred = predict_with_weights(final_x, final_weights)
    final_metrics = metrics(targets, final_pred)
    validation_pred = predict_with_weights(val_x, best[2])
    validation_metrics = metrics(val_y, validation_pred)

    model = AimDeltaModel(
        weights=final_weights,
        mean=final_mean,
        std=final_std,
        alpha=best_alpha,
        metadata={
            "model_type": "ridge_regression_poly2",
            "dataset_rows": int(len(targets)),
            "group_count": int(group_count),
            "validation_ratio": float(validation_ratio),
            "seed": int(seed),
            "selected_alpha": float(best_alpha),
        },
    )
    return model, alpha_results, validation_metrics, final_metrics, train_mask, val_mask


def make_report(total_rows, filtered_rows, model, alpha_results, validation_metrics, final_metrics, report_path, dataset_path):
    def line_metrics(prefix, values):
        return [
            f"- {prefix} yaw RMSE: `{values['rmse_yaw_deg']:.3f} deg`, MAE: `{values['mae_yaw_deg']:.3f} deg`, R2: `{values['r2_yaw']:.4f}`",
            f"- {prefix} pitch RMSE: `{values['rmse_pitch_deg']:.3f} deg`, MAE: `{values['mae_pitch_deg']:.3f} deg`, R2: `{values['r2_pitch']:.4f}`",
            f"- {prefix} within 1 deg both axes: `{values['within_1deg'] * 100:.2f}%`",
            f"- {prefix} within 0.5 deg both axes: `{values['within_05deg'] * 100:.2f}%`",
        ]

    lines = [
        "# Aim Delta Model Report",
        "",
        f"- Dataset: `{dataset_path}`",
        f"- Total rows: `{total_rows}`",
        f"- Training rows after filters: `{filtered_rows}`",
        f"- Model file: `{MODEL_PATH}`",
        f"- Selected ridge alpha: `{model.alpha}`",
        "",
        "## Validation Metrics",
        "",
    ]
    lines.extend(line_metrics("Validation", validation_metrics))
    lines.extend([
        "",
        "## Final Fit Metrics",
        "",
    ])
    lines.extend(line_metrics("Final", final_metrics))
    lines.extend([
        "",
        "## Alpha Search",
        "",
        "| alpha | yaw RMSE deg | pitch RMSE deg | within 1 deg |",
        "| ---: | ---: | ---: | ---: |",
    ])
    for result in alpha_results:
        lines.append(
            f"| {result['alpha']:.0e} | {result['rmse_yaw_deg']:.3f} | "
            f"{result['rmse_pitch_deg']:.3f} | {result['within_1deg'] * 100:.2f}% |"
        )

    output_path = Path(report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "\n".join(lines)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Train aim-delta ridge model.")
    parser.add_argument("--input", default=DATASET_PATH)
    parser.add_argument("--output", default=MODEL_PATH)
    parser.add_argument("--report", default=REPORT_PATH)
    parser.add_argument("--min-conf", type=float, default=0.25)
    parser.add_argument("--min-bbox-size", type=float, default=3.0)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser


def main():
    args = build_arg_parser().parse_args()
    data, total_rows = load_numeric_rows(args.input)
    mask = make_training_mask(data, args.min_conf, args.min_bbox_size)
    base, targets, groups = build_matrices(data, mask)
    model, alpha_results, validation_metrics, final_metrics, _, _ = train_and_evaluate(
        base,
        targets,
        groups,
        args.validation_ratio,
        args.seed,
    )
    model.save(args.output)
    report = make_report(
        total_rows,
        len(targets),
        model,
        alpha_results,
        validation_metrics,
        final_metrics,
        args.report,
        args.input,
    )
    print(report)


if __name__ == "__main__":
    main()
