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
| `F/H` | Move target left/right |
| `T/G` | Move target toward screen/launcher |
| `I/J/K/L` | Move viewer lookat |
| `Esc` | Quit |

## Main Files

- `conference_room_with_launcher.xml`: conference room world, launcher, and target model
- `view_world.py`: main conference room simulation
- `rubber_band_launcher.xml`: standalone launcher model
- `test.py`: standalone launcher simulation
- `progress_summary.md`: detailed project notes
- `yolo_model/target_yolo11s_640_best.onnx`: target detector used by the aim camera
