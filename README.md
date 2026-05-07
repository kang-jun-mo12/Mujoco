# MuJoCo Rubber Band Launcher

MuJoCo conference-room simulation with a two-axis rubber band launcher, an aim camera, and a movable target.
The aim camera can run a trained YOLO ONNX target detector on rendered MuJoCo frames.

## Run

```powershell
cd C:\Users\DESKTOP\Desktop\mujoco
.\.venv\Scripts\python.exe view_world.py
```

Use the OpenCV `Controls` window for keyboard input.

## Controls

| Key | Action |
| --- | --- |
| `W/S` | Pitch up/down by 1 degree |
| `A/D` | Yaw left/right by 1 degree |
| `Space` | Fire rubber band |
| `P` | Toggle aim camera |
| `O` | Run iterative YOLO-to-aim correction and fire once |
| `F/H` | Move target left/right |
| `T/G` | Move target toward screen/launcher |
| `I/J/K/L` | Move viewer lookat |
| `Esc` | Quit |

## Main Files

- `conference_room_with_launcher.xml`: conference room world, launcher, and target model
- `view_world.py`: main conference room simulation
- `collect_aim_dataset.py`: automated YOLO bbox to aim-delta CSV collector
- `analyze_aim_dataset.py`: dataset quality report generator
- `train_aim_delta_model.py`: ridge regression aim-delta trainer
- `aim_delta_model.py`: shared aim-delta model loader and predictor
- `rubber_band_launcher.xml`: standalone launcher model
- `test.py`: standalone launcher simulation
- `progress_summary.md`: detailed project notes
- `project_workflow.md`: completed work and next-step workflow
- `yolo_model/target_yolo11s_640_best.onnx`: target detector used by the aim camera

## Collect Aim Dataset

Generate CSV rows that connect YOLO bbox observations to the yaw/pitch delta needed to hit the target:

```powershell
.\.venv\Scripts\python.exe collect_aim_dataset.py --output datasets\aim_training_data.csv
```

Each row contains target position, bbox center/size/confidence, current yaw/pitch, hit yaw/pitch, and `delta_yaw` / `delta_pitch` labels.

## Train Aim Model

Analyze the collected 5cm dataset and train the first aim-delta regression model:

```powershell
.\.venv\Scripts\python.exe analyze_aim_dataset.py
.\.venv\Scripts\python.exe train_aim_delta_model.py
```

The trained model is saved to `models/aim_delta_ridge_5cm.npz`. In `view_world.py`, press `O` in the OpenCV `Controls` window to run several YOLO-to-aim correction iterations from the latest aim-camera view, then fire once.
