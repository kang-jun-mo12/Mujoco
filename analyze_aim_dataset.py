"""Analyze collected aim-delta CSV data and write a compact Markdown report."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

DATASET_PATH = "datasets/aim_training_data_5cm.csv"
REPORT_PATH = "reports/aim_dataset_quality_5cm.md"

NUMERIC_COLUMNS = [
    "target_x",
    "target_y",
    "bbox_w",
    "bbox_h",
    "bbox_area",
    "bbox_conf",
    "norm_err_x",
    "norm_err_y",
    "current_yaw_deg",
    "current_pitch_deg",
    "delta_yaw_deg",
    "delta_pitch_deg",
    "hit_time_sec",
    "hit_success",
]


def load_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def column_array(rows, name):
    return np.array([float(row[name]) for row in rows], dtype=np.float64)


def percentiles(values):
    ps = [0, 1, 5, 25, 50, 75, 95, 99, 100]
    vals = np.percentile(values, ps)
    return {p: vals[i] for i, p in enumerate(ps)}


def fmt_stats(values, unit=""):
    stats = percentiles(values)
    return (
        f"min {stats[0]:.4g}{unit}, p5 {stats[5]:.4g}{unit}, "
        f"median {stats[50]:.4g}{unit}, p95 {stats[95]:.4g}{unit}, "
        f"max {stats[100]:.4g}{unit}"
    )


def make_report(rows, dataset_path):
    arrays = {name: column_array(rows, name) for name in NUMERIC_COLUMNS}
    finite_mask = np.ones(len(rows), dtype=bool)
    for values in arrays.values():
        finite_mask &= np.isfinite(values)

    quality_mask = (
        finite_mask
        & (arrays["hit_success"] == 1)
        & (arrays["bbox_conf"] >= 0.25)
        & (arrays["bbox_w"] >= 3)
        & (arrays["bbox_h"] >= 3)
        & (np.abs(arrays["delta_yaw_deg"]) <= 5)
        & (np.abs(arrays["delta_pitch_deg"]) <= 4)
    )

    unique_positions = len({
        (round(float(row["target_x"]), 4), round(float(row["target_y"]), 4))
        for row in rows
    })

    lines = [
        "# Aim Dataset Quality Report",
        "",
        f"- Dataset: `{dataset_path}`",
        f"- Total rows: `{len(rows)}`",
        f"- Unique target positions with data: `{unique_positions}`",
        f"- Finite numeric rows: `{int(finite_mask.sum())}`",
        f"- Recommended training rows: `{int(quality_mask.sum())}`",
        "",
        "## Target Coverage",
        "",
        f"- X range: `{arrays['target_x'].min():.2f}m ~ {arrays['target_x'].max():.2f}m`",
        f"- Y range: `{arrays['target_y'].min():.2f}m ~ {arrays['target_y'].max():.2f}m`",
        "",
        "## Detection Stats",
        "",
        f"- Confidence: {fmt_stats(arrays['bbox_conf'])}",
        f"- BBox width: {fmt_stats(arrays['bbox_w'], ' px')}",
        f"- BBox height: {fmt_stats(arrays['bbox_h'], ' px')}",
        f"- BBox area: {fmt_stats(arrays['bbox_area'], ' px^2')}",
        "",
        "## Label Stats",
        "",
        f"- Delta yaw: {fmt_stats(arrays['delta_yaw_deg'], ' deg')}",
        f"- Delta pitch: {fmt_stats(arrays['delta_pitch_deg'], ' deg')}",
        f"- Hit time: {fmt_stats(arrays['hit_time_sec'], ' s')}",
        "",
        "## Recommended Filters",
        "",
        "- `hit_success == 1`",
        "- finite numeric values",
        "- `bbox_conf >= 0.25`",
        "- `bbox_w >= 3` and `bbox_h >= 3`",
        "- `abs(delta_yaw_deg) <= 5`",
        "- `abs(delta_pitch_deg) <= 4`",
    ]
    return "\n".join(lines) + "\n"


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Analyze aim dataset CSV quality.")
    parser.add_argument("--input", default=DATASET_PATH)
    parser.add_argument("--output", default=REPORT_PATH)
    return parser


def main():
    args = build_arg_parser().parse_args()
    rows = load_rows(args.input)
    report = make_report(rows, args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
