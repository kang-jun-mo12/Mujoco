# Aim Delta Model Report

- Dataset: `datasets/aim_training_data_5cm.csv`
- Total rows: `53207`
- Training rows after filters: `53207`
- Model file: `models/aim_delta_ridge_5cm.npz`
- Selected ridge alpha: `0.1`

## Validation Metrics

- Validation yaw RMSE: `0.834 deg`, MAE: `0.472 deg`, R2: `0.9122`
- Validation pitch RMSE: `1.090 deg`, MAE: `0.819 deg`, R2: `0.8023`
- Validation within 1 deg both axes: `64.28%`
- Validation within 0.5 deg both axes: `29.00%`

## Final Fit Metrics

- Final yaw RMSE: `0.839 deg`, MAE: `0.475 deg`, R2: `0.9112`
- Final pitch RMSE: `1.113 deg`, MAE: `0.843 deg`, R2: `0.7934`
- Final within 1 deg both axes: `62.83%`
- Final within 0.5 deg both axes: `29.34%`

## Alpha Search

| alpha | yaw RMSE deg | pitch RMSE deg | within 1 deg |
| ---: | ---: | ---: | ---: |
| 0e+00 | 0.877 | 3.638 | 44.66% |
| 1e-06 | 0.835 | 1.090 | 64.37% |
| 1e-04 | 0.835 | 1.090 | 64.37% |
| 1e-03 | 0.835 | 1.090 | 64.37% |
| 1e-02 | 0.834 | 1.090 | 64.37% |
| 1e-01 | 0.834 | 1.090 | 64.28% |
| 1e+00 | 0.834 | 1.092 | 64.17% |
| 1e+01 | 0.833 | 1.119 | 63.24% |
| 1e+02 | 0.837 | 1.194 | 59.58% |
