# MuJoCo 고무줄 발사대 프로젝트 설명

이 프로젝트는 MuJoCo 안에 회의실 환경을 만들고, 긴 회의 테이블 위에 2축 고무줄 발사대를 배치한 시뮬레이션입니다.  
포신에 달린 `aim_camera` 화면을 OpenCV 창으로 확인하고, 실제 환경 데이터로 학습한 YOLO 모델을 이용해 MuJoCo 안의 타겟을 검출합니다.

현재 목표는 YOLO가 본 타겟의 바운딩박스 정보로부터 발사대가 얼마나 yaw/pitch를 보정해야 하는지 학습 데이터를 만들고, 이후 자동 조준과 발사까지 연결하는 것입니다.

## 실행 환경

- 작업 폴더: `C:\Users\DESKTOP\Desktop\mujoco`
- OS/셸: Windows + PowerShell
- Python 가상환경: `.venv`
- 주요 라이브러리:
  - `mujoco`
  - `numpy`
  - `opencv-python`
  - `gymnasium[mujoco]`
  - `matplotlib`

기본 실행 명령:

```powershell
cd C:\Users\DESKTOP\Desktop\mujoco
.\.venv\Scripts\python.exe view_world.py
```

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `conference_room_with_launcher.xml` | 회의실 월드, 발사대, 고무줄, 이동식 타겟이 통합된 MuJoCo XML |
| `view_world.py` | 메인 실행 스크립트, 조작/발사/카메라/YOLO 추론 담당 |
| `collect_aim_dataset.py` | 타겟 위치별 YOLO bbox와 조준 보정량을 CSV로 수집하는 스크립트 |
| `rubber_band_launcher.xml` | 기존 단독 고무줄 발사대 XML |
| `test.py` | 기존 단독 발사대 실행 스크립트 |
| `README.md` | 깃허브용 간단 실행 설명 |
| `project_workflow.md` | 지금까지 한 작업과 앞으로 할 작업 흐름 정리 |
| `yolo_model/target_yolo11s_640_best.onnx` | Aim Camera 프레임에서 타겟을 검출하는 YOLO ONNX 모델 |

## 회의실 월드 구조

좌표계는 다음 기준으로 구성했습니다.

| 축 | 의미 |
| --- | --- |
| `+X` | 발사대가 바라보는 정면, 회의실 스크린 방향 |
| `+Y` | 테이블 좌우 방향 |
| `+Z` | 위쪽 |

월드에는 다음 구조물이 있습니다.

- 회의실 바닥
- 긴 회의 테이블
- 좌측/우측/정면 유리벽
- 유리창 너머 푸른 외부 배경
- 정면 검은 스크린
- 천장과 직사각형 조명
- 좌우 의자들
- 테이블 위 고무줄 발사대
- 테이블 위 이동식 타겟

회의실은 실제 사진과 비슷한 카메라 분위기를 내기 위해 조명, 유리벽 색, 외부 배경색, 테이블 색을 여러 번 보정했습니다.

## 테이블

테이블은 `long_table` body 안의 `long_table_top` 단일 box geom으로 구현되어 있습니다.

```xml
<geom name="long_table_top" type="box" pos="0 0 0" size="3.6 0.9 0.045" material="table_mat"/>
```

MuJoCo의 box `size`는 반쪽 길이이므로 실제 테이블 크기는 다음과 같습니다.

- X 방향 길이: `7.2m`
- Y 방향 폭: `1.8m`
- X 범위: `-3.0m ~ 4.2m`
- Y 범위: `-0.9m ~ 0.9m`

테이블 중앙선과 가장자리처럼 위로 튀어나와 있던 부분은 제거했고, 현재는 전체가 평평한 하나의 상판입니다.  
테이블 색은 Aim Camera 화면에서 `#C8A28D rgba(200, 162, 141, 1.00)`에 가깝게 보이도록 조명 반사를 고려해 XML material 값을 낮게 보정했습니다.

```xml
<material name="table_mat" rgba="0.43 0.273 0.18 1" reflectance="0"/>
```

## 유리벽과 외부 배경

왼쪽, 오른쪽, 정면 벽은 유리 패널 구조로 맞췄습니다.  
정면 스크린 뒤 벽도 좌우 유리벽과 같은 구조를 사용합니다.

유리창 너머 색은 Aim Camera 화면 기준으로 `#6C8BAA rgba(108, 139, 170, 1.00)`에 가깝게 보이도록 보정했습니다.

```xml
<texture type="skybox" name="skybox" builtin="gradient" rgb1="0.22 0.27 0.25" rgb2="0.22 0.27 0.25"/>
<material name="glass_mat" rgba="0.12 0.16 0.14 0.28" reflectance="0.02"/>
<material name="outside_view_mat" rgba="0.22 0.27 0.25 1" reflectance="0"/>
```

## 발사대 구조

발사대는 회의 테이블의 `-X` 끝 중앙, `y=0`에 배치되어 있고, 포신은 월드 `+X` 방향인 스크린 방향을 바라봅니다.

반드시 유지해야 하는 이름들은 현재 XML에서 그대로 유지되어 있습니다.

- `yaw_joint`
- `pitch_joint`
- `yaw_motor`
- `pitch_motor`
- `rubber_projectile`
- `muzzle_site`
- `aim_camera`

현재 actuator는 2개만 사용합니다.

| actuator | 연결 joint | 역할 |
| --- | --- | --- |
| `yaw_motor` | `yaw_joint` | 좌우 조향 |
| `pitch_motor` | `pitch_joint` | 상하 조향 |

`trigger_joint`, `trigger_motor`, trigger actuator는 없습니다.  
발사는 서보모터가 아니라 Python의 `do_fire()` 함수에서 같은 `rubber_projectile` body를 포구 위치로 재배치하고 포신 방향 속도를 주는 방식입니다.

발사대 내부 geom끼리 충돌해서 yaw 회전이 막히지 않도록 launcher visual geom에는 내부 충돌 off 설정을 유지했습니다.

```xml
<default class="launcher_visual">
  <geom contype="0" conaffinity="0"/>
</default>
```

## 조작 방식

MuJoCo viewer에는 프로젝트 키 입력을 직접 바인딩하지 않습니다.  
viewer는 보기 전용이며, 프로젝트 조작은 OpenCV `Controls` 창에서 받습니다.

| 키 | 기능 |
| --- | --- |
| `W` | pitch 위로 1도 조정 |
| `S` | pitch 아래로 1도 조정 |
| `A` | yaw 왼쪽으로 1도 조정 |
| `D` | yaw 오른쪽으로 1도 조정 |
| `Space` | 고무줄 발사 |
| `P` | Aim Camera 창 켜기/끄기 |
| `O` | YOLO bbox 기반 조준 보정 모델을 한 번 적용 |
| `Esc` | 종료 |
| `F` | 타겟을 월드 `+Y` 방향으로 이동 |
| `H` | 타겟을 월드 `-Y` 방향으로 이동 |
| `T` | 타겟을 스크린 방향, 월드 `+X` 방향으로 이동 |
| `G` | 타겟을 발사대 방향, 월드 `-X` 방향으로 이동 |
| `I` | viewer lookat을 월드 `+X` 방향으로 이동 |
| `K` | viewer lookat을 월드 `-X` 방향으로 이동 |
| `J` | viewer lookat을 월드 `+Y` 방향으로 이동 |
| `L` | viewer lookat을 월드 `-Y` 방향으로 이동 |

현재 조향 step:

```python
YAW_STEP = np.deg2rad(1)
PITCH_STEP = np.deg2rad(1)
```

타겟 이동 step:

```python
TARGET_MOVE_STEP = 0.01
```

viewer 전지적 시점 이동 step:

```python
VIEW_MOVE_STEP = 0.20
```

## Aim Camera

`aim_camera`는 포신 근처에 달린 실제 장치 카메라 역할입니다.  
포신이 yaw/pitch로 움직이면 aim camera도 같이 움직입니다.

```xml
<camera name="aim_camera" pos="0.30 0 -0.13" xyaxes="0 -1 0  0 0 1" fovy="76"/>
```

현재 카메라 렌더링 사양:

```python
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
TARGET_FPS = 30
```

한때 `2592 x 1944`로 변경했지만, OpenCV 창 안정성과 처리 속도 문제 때문에 원래 사양인 `640 x 480`으로 되돌렸습니다.  
Aim Camera 화면에는 yaw/pitch, fire_count, YOLO bbox, bbox 중심, 화면 중심 기준 오차가 overlay로 표시됩니다.

## 고무줄 발사와 바운스

고무줄은 `rubber_projectile` body 하나를 반복 재사용합니다.  
`Space`를 누를 때마다 같은 body를 `muzzle_site` 위치로 옮기고 포신 방향으로 초기 속도를 줍니다.

```python
LAUNCH_SPEED = 12.0
```

고무줄 색은 노란색입니다.  
`R` 재장전 기능은 제거되어 있고, `Space`를 누르면 매번 자동으로 재배치 후 발사합니다.

바닥이나 테이블에 닿았을 때 여러 번 강하게 튀지 않도록 첫 충돌만 약하게 튀고, 두 번째 충돌부터는 멈추는 방식으로 제어합니다.

```python
FIRST_BOUNCE_HORIZONTAL_SCALE = 0.65
FIRST_BOUNCE_VERTICAL_SCALE = 0.25
FIRST_BOUNCE_ANGULAR_SCALE = 0.25
```

## 타겟 오브젝트

타겟은 실제 사진에 있는 모양을 기준으로 만들었습니다.  
아래 직사각형, 세로 막대, 위쪽 원형 머리로 구성되어 있습니다.

현재 XML 구현:

```xml
<body name="target_object" mocap="true" pos="-1.20 0 0.805">
  <geom name="target_base_rect" type="box" pos="0 0 0" size="0.0054 0.045 0.018" material="target_mat"/>
  <geom name="target_stem" type="box" pos="0 0 0.054" size="0.0054 0.0135 0.036" material="target_mat"/>
  <geom name="target_round_head" type="sphere" pos="0 0 0.108" size="0.036" material="target_mat"/>
</body>
```

타겟은 너무 작게 보였기 때문에 원래 규격보다 전체적으로 크게 만들었습니다.  
색은 Aim Camera 기준 `#7A4F46 rgba(122, 79, 70, 1.00)`에 가깝게 보이도록 보정했습니다.

```xml
<material name="target_mat" rgba="0.392 0.181 0.117 1" reflectance="0"/>
```

타겟은 `mocap="true"` body로 구현되어 있어 Python에서 `data.mocap_pos`를 바꿔 위치를 이동합니다.  
고무줄과 충돌할 수 있도록 target geom의 collision은 꺼두지 않았습니다.

## YOLO 추론

실제 환경에서 수집한 데이터로 학습한 YOLO 모델을 MuJoCo Aim Camera 프레임에 적용합니다.

사용 모델:

```python
YOLO_MODEL_PATH = "yolo_model/target_yolo11s_640_best.onnx"
YOLO_INPUT_SIZE = 640
YOLO_CONF_THRESHOLD = 0.25
YOLO_NMS_THRESHOLD = 0.45
YOLO_INFER_EVERY_N_FRAMES = 3
```

추론 흐름:

1. MuJoCo Aim Camera를 `640 x 480`으로 렌더링합니다.
2. 실제 웹캠처럼 보이도록 색감, 밝기, bloom, blur 후처리를 적용합니다.
3. YOLO 입력 크기 `640 x 640`에 맞게 letterbox 처리합니다.
4. OpenCV DNN으로 ONNX 모델을 실행합니다.
5. bbox를 원래 `640 x 480` 좌표로 되돌립니다.
6. 가장 confidence가 높은 타겟 bbox를 사용합니다.
7. bbox 중심과 화면 중심의 차이를 계산해 overlay와 Controls 창에 표시합니다.

모델 출력 shape는 현재 `(1, 5, 8400)` 구조로 확인되어 있습니다.  
클래스는 `target` 하나입니다.

## 조준 보정 모델

5cm 전체 테이블 데이터셋으로 첫 조준 보정 회귀 모델을 학습했습니다.  
모델은 YOLO bbox feature와 현재 yaw/pitch를 입력으로 받아 현재 포신 방향에서 목표를 맞추기 위해 얼마나 움직여야 하는지 예측합니다.

모델 파일:

```text
models/aim_delta_ridge_5cm.npz
```

학습/분석 스크립트:

```powershell
.\.venv\Scripts\python.exe analyze_aim_dataset.py
.\.venv\Scripts\python.exe train_aim_delta_model.py
```

사용 feature:

- `norm_err_x`, `norm_err_y`
- `bbox_w_norm`, `bbox_h_norm`, `bbox_area_norm`
- `bbox_conf`
- `current_yaw_rad`, `current_pitch_rad`
- 위 feature들의 2차항과 상호작용항

검증 성능:

```text
yaw RMSE:   약 0.834 deg
pitch RMSE: 약 1.090 deg
both axes within 1 deg: 약 64.28%
```

`view_world.py`에서는 OpenCV `Controls` 창에 포커스를 둔 상태에서 `O`를 누르면 최신 YOLO bbox 기준으로 예측된 `delta_yaw`, `delta_pitch`를 한 번 적용합니다.  
발사는 여전히 `Space`로 직접 실행합니다.

## 조준 데이터 수집

`collect_aim_dataset.py`는 자동 조준 학습용 CSV를 만드는 스크립트입니다.

핵심 아이디어는 절대 서보모터 값이 아니라, 현재 카메라가 바라보는 방향에서 타겟을 맞추기 위해 얼마나 움직여야 하는지인 보정량을 저장하는 것입니다.  
카메라가 포신에 붙어 있어서 포신이 움직이면 카메라 화면도 같이 바뀌기 때문에, `hit_yaw`, `hit_pitch` 자체보다 `delta_yaw`, `delta_pitch`가 더 중요한 label입니다.

```text
delta_yaw   = hit_yaw   - current_yaw
delta_pitch = hit_pitch - current_pitch
```

기본 실행:

```powershell
.\.venv\Scripts\python.exe collect_aim_dataset.py --output datasets\aim_training_data.csv
```

CSV 주요 컬럼:

```text
target_x,target_y,target_z
bbox_x1,bbox_y1,bbox_x2,bbox_y2
bbox_cx,bbox_cy,bbox_w,bbox_h,bbox_area,bbox_conf
norm_err_x,norm_err_y,bbox_w_norm,bbox_h_norm,bbox_area_norm
current_yaw_deg,current_pitch_deg
hit_yaw_deg,hit_pitch_deg
delta_yaw_deg,delta_pitch_deg
hit_time_sec,hit_success
```

수집 과정:

1. 타겟을 테이블 위 grid 위치로 이동합니다.
2. 해당 위치를 맞출 수 있는 `hit_yaw`, `hit_pitch`를 MuJoCo 발사 시뮬레이션으로 찾습니다.
3. 명중 각도 주변에 여러 current yaw/pitch 상태를 만듭니다.
4. 각 상태에서 Aim Camera를 렌더링합니다.
5. YOLO로 bbox를 검출합니다.
6. bbox feature와 `delta_yaw`, `delta_pitch` label을 CSV에 기록합니다.

기본 grid는 빠른 실험용으로 일부 영역만 사용합니다.

```text
x: -1.8m ~ 3.0m
y: -0.6m ~ 0.6m
step: 0.3m
```

이 설정은 전체 테이블이 아니라 안전하고 빠른 coarse grid입니다.  
전체 테이블을 쓰려면 아래 범위를 사용해야 합니다.

```text
x: -3.0m ~ 4.2m
y: -0.9m ~ 0.9m
```

예시:

```powershell
.\.venv\Scripts\python.exe collect_aim_dataset.py `
  --output datasets\aim_training_data.csv `
  --x-min -3.0 --x-max 4.2 `
  --y-min -0.9 --y-max 0.9 `
  --position-step 0.1
```

## 데이터 수집 시간 예상

현재 PC CPU는 확인 결과 다음과 같습니다.

```text
AMD Ryzen 5 3500
6 cores / 6 logical processors
Max clock 약 3.59GHz
```

이 PC에서 벤치마크한 결과, 데이터 수집은 타겟 위치 1개당 약 `6.4초` 정도 걸렸습니다.

비교 대상인 `12th Gen Intel Core i5-12400F`는 6코어 12스레드 CPU이며, PassMark 기준으로 Ryzen 5 3500보다 대략 1.4~1.5배 빠른 편입니다.  
따라서 같은 코드 기준으로는 위치 1개당 약 `4.2~4.6초` 정도를 예상할 수 있습니다.

| 그리드 간격 | 위치 수 | Ryzen 5 3500 예상 | i5-12400F 예상 |
| --- | ---: | ---: | ---: |
| 기본 grid | 85개 | 약 9분 | 약 6~7분 |
| 30cm 전체 테이블 | 약 175개 | 약 19분 | 약 12~14분 |
| 10cm 전체 테이블 | 약 1387개 | 약 2시간 28분 | 약 1시간 36분~1시간 46분 |
| 5cm 전체 테이블 | 약 5365개 | 약 9시간 32분 | 약 6시간 13분~6시간 49분 |
| 2cm 전체 테이블 | 약 32851개 | 약 58시간 | 약 38~42시간 |

토큰은 데이터 수집 중 계속 소모되는 것이 아닙니다.  
시간이 오래 걸리는 부분은 사용자의 컴퓨터에서 돌아가는 MuJoCo 시뮬레이션, 렌더링, YOLO 추론 계산입니다.

## 5cm 전체 테이블 데이터 수집 결과

2026년 5월 7일에 전체 테이블 범위를 `5cm` 간격으로 4분할 병렬 수집했습니다.

```text
x: -3.0m ~ 4.2m
y: -0.9m ~ 0.9m
step: 0.05m
```

| part | x 범위 | 결과 row |
| --- | --- | ---: |
| part1 | `-3.00 ~ -1.25` | 6940 |
| part2 | `-1.20 ~ 0.55` | 19761 |
| part3 | `0.60 ~ 2.35` | 16914 |
| part4 | `2.40 ~ 4.20` | 9592 |

최종 병합 파일:

```text
datasets/aim_training_data_5cm.csv
```

검증 결과:

```text
data rows: 53207
file size: 약 18.64MB
header count: 1
```

실제 수집은 대략 오전 6시 3분부터 오전 9시 52분까지 진행되어 약 3시간 49분 정도 걸렸습니다.  
데이터 파일은 크기가 크고 생성물 성격이므로 `datasets/` 폴더를 `.gitignore`에 넣어 GitHub에는 올리지 않습니다.

## 현재 검증된 내용

- 회의실 통합 XML 로드 가능
- OpenCV `Controls` 창에서 키 입력 처리
- MuJoCo viewer는 보기 전용 유지
- yaw/pitch 2개 actuator 구조 유지
- trigger 관련 joint/motor 없음
- Space 반복 발사 가능
- R 재장전 기능 없음
- 발사대 yaw lock 문제 해결
- Aim Camera가 포신 방향과 정렬됨
- Aim Camera 사양은 `640 x 480`, `30 FPS`
- 타겟 이동 `F/H/T/G` 동작
- viewer lookat 이동 `I/J/K/L` 동작
- YOLO ONNX 모델로 MuJoCo 타겟 검출 가능
- 데이터 수집 스크립트 smoke test 성공
- 데이터 수집 benchmark로 시간 추정 완료
- 데이터 수집 진행 상황이 CSV와 로그에 바로 남도록 flush 처리 추가
- 5cm 간격 전체 테이블 병렬 데이터 수집 완료
- 5cm 데이터 기반 ridge 회귀 조준 보정 모델 학습 완료
- `O` 키로 YOLO bbox 기반 1회 자동 조준 보정 적용 가능

## 앞으로의 핵심 방향

다음 단계는 현재 ridge 회귀 모델의 실제 명중률을 `view_world.py`에서 테스트하고, 부족하면 데이터 정제나 더 강한 모델로 개선하는 것입니다.  
모델 보정이 안정적으로 맞기 시작하면 YOLO 검출, 자동 보정, 발사를 하나의 자동 루프로 연결할 수 있습니다.
