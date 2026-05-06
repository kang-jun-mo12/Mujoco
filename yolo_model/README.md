# MuJoCo YOLO Target Detector

This package contains the trained target detector for 640x480 MuJoCo aim camera inference.

## Files

- `target_yolo11s_640_best.pt`: Ultralytics/PyTorch model.
- `target_yolo11s_640_best.onnx`: ONNX export for deployment.
- `data.yaml`: YOLO class metadata.
- `classes.txt`: Class names, one per line.

## Model Input

- Camera resolution: 640x480
- Training image size: 640
- Class: `target`

## Ultralytics Python Example

```python
from ultralytics import YOLO

model = YOLO("target_yolo11s_640_best.pt")
results = model(frame_bgr, imgsz=640, conf=0.25, device=0)

for box in results[0].boxes:
    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
    conf = float(box.conf[0])
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
```

## Screen Center Error

For MuJoCo aim control:

```python
error_x = cx - 640 / 2
error_y = cy - 480 / 2
norm_x = error_x / (640 / 2)
norm_y = error_y / (480 / 2)
```
