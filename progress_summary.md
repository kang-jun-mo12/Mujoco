# MuJoCo 고무줄 발사대 프로젝트 전체 설명

이 프로젝트는 MuJoCo 안에 회의실 환경을 만들고, 긴 회의 테이블 위에 2축 고무줄 발사대를 배치한 시뮬레이션입니다. 포신에 달린 `aim_camera` 화면을 OpenCV 창으로 확인하고, 실제 환경 데이터로 학습한 YOLO 모델을 이용해 MuJoCo 안의 타겟을 검출합니다.

현재는 YOLO bbox 정보를 이용해 발사대의 yaw/pitch 보정량을 예측하고, `O` 키를 누르면 자동 조준 보정 후 고무줄을 1회 발사하는 단계까지 구현되어 있습니다.

## 실행 환경

- 작업 폴더: `C:\Users\DESKTOP\Desktop\mujoco`
- OS/셸: Windows + PowerShell
- Python 가상환경: `.venv`
- 주요 라이브러리:
  - `mujoco`
  - `opencv-python`
  - `numpy`
  - `gymnasium[mujoco]`
  - `matplotlib`

실행 명령:

```powershell
cd C:\Users\DESKTOP\Desktop\mujoco
.\.venv\Scripts\python.exe view_world.py
```

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `conference_room_with_launcher.xml` | 회의실 월드, 발사대, 고무줄, 타겟, 명중 파티클 효과가 통합된 MuJoCo XML |
| `view_world.py` | 메인 실행 스크립트, 조작/발사/카메라/YOLO/자동조준 담당 |
| `aim_delta_model.py` | 조준 보정 모델 로드와 예측 함수 |
| `models/aim_delta_ridge_5cm.npz` | 5cm 데이터셋으로 학습한 조준 보정 모델 |
| `collect_aim_dataset.py` | 타겟 위치별 YOLO bbox와 조준 보정량을 CSV로 수집 |
| `analyze_aim_dataset.py` | 수집 데이터 품질 리포트 생성 |
| `train_aim_delta_model.py` | ridge regression 조준 보정 모델 학습 |
| `reports/aim_dataset_quality_5cm.md` | 5cm 데이터셋 품질 리포트 |
| `reports/aim_delta_model_5cm.md` | 조준 보정 모델 성능 리포트 |
| `yolo_model/target_yolo11s_640_best.onnx` | Aim Camera 프레임에서 타겟을 검출하는 YOLO ONNX 모델 |
| `README.md` | GitHub용 실행 안내 |
| `project_workflow.md` | 지금까지 한 작업과 다음 작업 흐름 |

## 월드 좌표계

| 축 | 의미 |
| --- | --- |
| `+X` | 발사대가 바라보는 정면, 스크린 방향 |
| `+Y` | 테이블 좌우 방향 |
| `+Z` | 위쪽 |

회의실 월드에는 바닥, 긴 테이블, 좌우/정면 유리벽, 유리창 너머 배경, 정면 스크린, 천장 조명, 의자, 발사대, 타겟이 포함되어 있습니다.

## 회의실과 테이블

테이블은 `long_table_top` 단일 box geom으로 구현되어 있고, 전체가 평평한 상판입니다.

```xml
<geom name="long_table_top" type="box" pos="0 0 0" size="3.6 0.9 0.045" material="table_mat"/>
```

MuJoCo box `size`는 반쪽 길이이므로 실제 테이블 범위는 다음과 같습니다.

```text
X 길이: 7.2m
Y 폭: 1.8m
X 범위: -3.0m ~ 4.2m
Y 범위: -0.9m ~ 0.9m
```

테이블 색은 Aim Camera 화면 기준 `#C8A28D rgba(200, 162, 141, 1.00)`에 가깝게 보이도록 보정했습니다.

```xml
<material name="table_mat" rgba="0.43 0.273 0.18 1" reflectance="0"/>
```

좌우/정면 유리창 너머 배경은 Aim Camera 화면 기준 `#6C8BAA rgba(108, 139, 170, 1.00)`에 가깝게 보이도록 조정했습니다.

## 발사대 구조

발사대는 테이블의 `-X` 끝 중앙, `y=0`에 배치되어 있고, 포신은 월드 `+X` 방향인 스크린 방향을 바라봅니다.

반드시 유지되는 이름:

- `yaw_joint`
- `pitch_joint`
- `yaw_motor`
- `pitch_motor`
- `rubber_projectile`
- `muzzle_site`
- `aim_camera`

현재 actuator는 2개뿐입니다.

| actuator | joint | 역할 |
| --- | --- | --- |
| `yaw_motor` | `yaw_joint` | 좌우 조향 |
| `pitch_motor` | `pitch_joint` | 상하 조향 |

`trigger_joint`, `trigger_motor`, trigger actuator는 없습니다. 발사는 Python의 `do_fire()`가 `rubber_projectile`을 포구 위치로 재배치하고 포신 방향 속도를 주는 방식입니다.

발사대 내부 geom끼리 충돌해서 yaw가 잠기지 않도록 launcher visual geom의 내부 충돌은 꺼두었습니다.

## 조작 방식

MuJoCo viewer는 보기 전용입니다. 프로젝트 조작은 OpenCV `Controls` 창에서 받습니다.

| 키 | 기능 |
| --- | --- |
| `W/S` | pitch 위/아래 1도 조정 |
| `A/D` | yaw 좌/우 1도 조정 |
| `Space` | 고무줄 수동 발사 |
| `P` | Aim Camera 창 켜기/끄기 |
| `O` | YOLO bbox 기반 반복 자동 조준 후 고무줄 1회 발사 |
| `F/H` | 타겟을 월드 `+Y/-Y` 방향으로 이동 |
| `T/G` | 타겟을 스크린/발사대 방향으로 이동 |
| `I/J/K/L` | viewer lookat 이동 |
| `Esc` | 종료 |

현재 step 값:

```python
YAW_STEP = np.deg2rad(1)
PITCH_STEP = np.deg2rad(1)
TARGET_MOVE_STEP = 0.01
VIEW_MOVE_STEP = 0.20
```

## Aim Camera

`aim_camera`는 포신 근처에 달린 실제 장치 카메라 역할입니다. 포신이 움직이면 Aim Camera도 같이 움직입니다.

```xml
<camera name="aim_camera" pos="0.30 0 -0.13" xyaxes="0 -1 0  0 0 1" fovy="76"/>
```

현재 사양:

```python
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
TARGET_FPS = 30
```

Aim Camera 화면에는 yaw/pitch, 발사 횟수, YOLO bbox와 label/confidence, 명중 시 `HIT!` 텍스트가 표시됩니다. 사용자가 요청해서 화면 중앙 에임포인트, bbox 중심점, 노란 연결선, 하단 err 텍스트는 제거했습니다. 내부 자동조준 계산에는 bbox 중심 오차값을 계속 사용합니다.

## 타겟 오브젝트

타겟은 실제 사진을 기준으로 아래 직사각형, 세로 막대, 위쪽 원형 머리 구조로 만들었습니다.

```xml
<body name="target_object" mocap="true" pos="-1.20 0 0.805">
  <geom name="target_base_rect" type="box" pos="0 0 0" size="0.0054 0.045 0.018" material="target_mat"/>
  <geom name="target_stem" type="box" pos="0 0 0.054" size="0.0054 0.0135 0.036" material="target_mat"/>
  <geom name="target_round_head" type="sphere" pos="0 0 0.108" size="0.036" material="target_mat"/>
</body>
```

색은 Aim Camera 기준 `#7A4F46 rgba(122, 79, 70, 1.00)`에 가깝게 보이도록 보정했습니다. 타겟은 `mocap="true"` body이며, Python에서 `data.mocap_pos`로 이동합니다.

## 고무줄 발사와 바운스

고무줄은 `rubber_projectile` body 하나를 반복 재사용합니다. `Space`를 누르거나 `O` 자동 조준이 끝나면 `do_fire()`가 같은 body를 포구 위치로 옮기고 초기 속도를 줍니다.

```python
LAUNCH_SPEED = 12.0
```

`R` 재장전 키는 없습니다. `Space` 또는 `O` 발사 때마다 자동으로 재배치됩니다.

첫 충돌은 약하게 튀고, 두 번째 충돌부터는 멈추도록 제어합니다.

```python
FIRST_BOUNCE_HORIZONTAL_SCALE = 0.65
FIRST_BOUNCE_VERTICAL_SCALE = 0.25
FIRST_BOUNCE_ANGULAR_SCALE = 0.25
```

## 명중 시각 효과

고무줄 geom `rb_1` ~ `rb_4`가 타겟 geom `target_base_rect`, `target_stem`, `target_round_head`와 contact되면 명중으로 판정합니다.

명중 시:

- `hit_effect` mocap body가 충돌 위치로 이동합니다.
- `hit_particle_0` ~ `hit_particle_8` sphere가 짧게 퍼집니다.
- Aim Camera 화면에 `HIT! #n`이 표시됩니다.
- Controls 창에 누적 hit count가 표시됩니다.

## YOLO 타겟 검출

실제 환경 데이터로 학습한 YOLO ONNX 모델을 MuJoCo Aim Camera 프레임에 적용합니다.

```python
YOLO_MODEL_PATH = "yolo_model/target_yolo11s_640_best.onnx"
YOLO_INPUT_SIZE = 640
YOLO_CONF_THRESHOLD = 0.25
YOLO_NMS_THRESHOLD = 0.45
YOLO_INFER_EVERY_N_FRAMES = 3
```

추론 흐름:

1. Aim Camera를 `640 x 480`으로 렌더링합니다.
2. 웹캠처럼 보이도록 색감, 밝기, bloom, blur 후처리를 적용합니다.
3. YOLO 입력 크기 `640 x 640`으로 letterbox 처리합니다.
4. OpenCV DNN으로 ONNX 모델을 실행합니다.
5. bbox를 원래 `640 x 480` 좌표로 되돌립니다.
6. 가장 confidence가 높은 bbox를 사용합니다.

YOLO 모델 출력 shape는 `(1, 5, 8400)`으로 확인되어 있고 클래스는 `target` 하나입니다.

## 조준 보정 모델

5cm 전체 테이블 데이터셋으로 ridge regression 기반 조준 보정 모델을 학습했습니다.

모델 파일:

```text
models/aim_delta_ridge_5cm.npz
```

입력 feature:

- `norm_err_x`, `norm_err_y`
- `bbox_w_norm`, `bbox_h_norm`, `bbox_area_norm`
- `bbox_conf`
- `current_yaw_rad`, `current_pitch_rad`
- 위 feature들의 2차항과 상호작용항

예측 label:

- `delta_yaw_rad`
- `delta_pitch_rad`

검증 성능:

```text
yaw RMSE: 0.834 deg
pitch RMSE: 1.090 deg
both axes within 1 deg: 64.28%
```

`O` 키 동작:

```text
Aim Camera 렌더링
-> YOLO 검출
-> 보정량 예측
-> yaw/pitch 적용
-> 조향 안정화
-> 최대 6회 반복
-> 최종 타겟 검출이 남아 있으면 do_fire()로 1회 발사
```

타겟이 검출되지 않으면 안전하게 발사하지 않습니다.

## 조준 데이터 수집

`collect_aim_dataset.py`는 자동 조준 학습용 CSV를 만드는 스크립트입니다.

핵심 label은 절대 서보모터 각도가 아니라 현재 포신 방향 기준 보정량입니다.

```text
delta_yaw   = hit_yaw   - current_yaw
delta_pitch = hit_pitch - current_pitch
```

기본 실행:

```powershell
.\.venv\Scripts\python.exe collect_aim_dataset.py --output datasets\aim_training_data.csv
```

5cm 전체 테이블 수집 결과:

```text
파일: datasets/aim_training_data_5cm.csv
data rows: 53207
file size: 약 18.64MB
수집 시간: 약 3시간 49분
```

`datasets/` 폴더는 `.gitignore`에 포함되어 있어 GitHub에는 올라가지 않습니다.

## 데이터 분석과 학습

```powershell
.\.venv\Scripts\python.exe analyze_aim_dataset.py
.\.venv\Scripts\python.exe train_aim_delta_model.py
```

생성 결과:

- `reports/aim_dataset_quality_5cm.md`
- `reports/aim_delta_model_5cm.md`
- `models/aim_delta_ridge_5cm.npz`

## GitHub 클론 실행

노트북에서 클론해도 실행, YOLO 검출, `O` 자동 조준/발사는 가능합니다.

```powershell
git clone https://github.com/kang-jun-mo12/Mujoco.git
cd Mujoco
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe view_world.py
```

단, `datasets/aim_training_data_5cm.csv`는 GitHub에 없으므로 데이터 분석/재학습을 하려면 따로 복사해야 합니다. 이미 학습된 모델 파일은 GitHub에 포함되어 있어 실행에는 데이터셋 CSV가 필요 없습니다.

## 현재 검증된 내용

- 회의실 통합 XML 로드 가능
- MuJoCo viewer 보기 전용 유지
- OpenCV `Controls` 입력 처리
- yaw/pitch 2축 actuator 구조 유지
- trigger 관련 joint/motor 없음
- Space 반복 발사 가능
- O 자동 조준 후 1회 발사 가능
- Aim Camera와 포신 방향 정렬
- YOLO ONNX 타겟 검출 가능
- 5cm 전체 테이블 데이터 수집 완료
- ridge regression 조준 보정 모델 학습 완료
- 명중 시 파티클 효과와 `HIT!` 표시 가능

## 앞으로의 방향

다음 단계는 여러 타겟 위치에서 `O` 자동 조준/발사의 실제 명중률을 기록하고, 실패 사례를 분석하는 것입니다. 필요하면 데이터 정제, 더 강한 회귀 모델, 자동 평가 루프를 추가해 명중률을 개선합니다.
