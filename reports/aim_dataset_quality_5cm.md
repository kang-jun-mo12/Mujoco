# Aim Dataset Quality Report

- Dataset: `datasets/aim_training_data_5cm.csv`
- Total rows: `53207`
- Unique target positions with data: `4313`
- Finite numeric rows: `53207`
- Recommended training rows: `53207`

## Target Coverage

- X range: `-2.25m ~ 4.20m`
- Y range: `-0.90m ~ 0.90m`

## Detection Stats

- Confidence: min 0.25, p5 0.3224, median 0.6805, p95 0.8394, max 0.9039
- BBox width: min 3 px, p5 5 px, median 10 px, p95 86 px, max 222 px
- BBox height: min 6 px, p5 8 px, median 20 px, p95 155 px, max 398 px
- BBox area: min 27 px^2, p5 45 px^2, median 200 px^2, p95 1.395e+04 px^2, max 7.925e+04 px^2

## Label Stats

- Delta yaw: min -4 deg, p5 -4 deg, median 0 deg, p95 4 deg, max 4 deg
- Delta pitch: min -3 deg, p5 -3 deg, median 0 deg, p95 3 deg, max 3 deg
- Hit time: min 0.028 s, p5 0.078 s, median 0.252 s, p95 0.5 s, max 0.568 s

## Recommended Filters

- `hit_success == 1`
- finite numeric values
- `bbox_conf >= 0.25`
- `bbox_w >= 3` and `bbox_h >= 3`
- `abs(delta_yaw_deg) <= 5`
- `abs(delta_pitch_deg) <= 4`
