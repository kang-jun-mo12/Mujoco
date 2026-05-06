# MuJoCo 고무줄 발사대 회의실 시뮬레이션 설명

이 프로젝트는 MuJoCo로 2축 서보모터 기반 고무줄 발사대를 구현하고, 이를 회의실 월드 안의 긴 테이블 위에 배치한 시뮬레이션입니다.  
조작 입력은 MuJoCo viewer가 아니라 OpenCV `Controls` 창에서 받고, MuJoCo viewer는 전체 회의실을 보는 전지적 시점으로 사용합니다.

## 실행 환경

현재 프로젝트는 Windows + PowerShell 환경에서 진행 중입니다.

- 작업 폴더: `C:\Users\DESKTOP\Desktop\mujoco`
- Python 가상환경: `.venv`
- MuJoCo: `mujoco`
- OpenCV: `cv2`
- NumPy: `numpy`

`requirements.txt` 기준 의존성은 다음과 같습니다.

```text
mujoco>=3.0.0
gymnasium[mujoco]>=1.0.0
numpy>=2.0.0
matplotlib>=3.7.0
```

현재 실행 스크립트에서는 `mujoco`, `mujoco.viewer`, `numpy`, `cv2`, `threading`, `time`을 사용합니다.

## 주요 파일

- `conference_room_with_launcher.xml`
  - 회의실 월드와 launcher가 통합된 MuJoCo XML입니다.
  - 현재 주 실행 대상입니다.
- `view_world.py`
  - 회의실 월드를 실행하는 Python 스크립트입니다.
  - 키 입력, 발사, 조준 카메라, viewer 카메라 이동, 타겟 이동, 고무줄 튕김 제어를 담당합니다.
- `rubber_band_launcher.xml`
  - 기존 단독 launcher 모델입니다.
- `test.py`
  - 기존 단독 launcher 실행 스크립트입니다.
  - 조작 방식과 튕김 제어는 `view_world.py`와 같은 방향으로 유지됩니다.
- `progress_summary.md`
  - 현재 프로젝트 구조와 구현 내용을 설명하는 문서입니다.

## 실행 방법

회의실 월드는 다음 명령으로 실행합니다.

```powershell
cd C:\Users\DESKTOP\Desktop\mujoco
.\.venv\Scripts\python.exe view_world.py
```

실행하면 다음 창이 사용됩니다.

- MuJoCo viewer: 전체 회의실을 보는 전지적 시점
- `Controls`: 키 입력용 OpenCV 창
- `Aim Camera`: `P` 키로 켜고 끄는 포신 시점 카메라 창

키 입력은 반드시 `Controls` 창에 포커스를 둔 상태에서 해야 합니다.

## 회의실 월드 구성

좌표계는 다음 기준으로 구성되어 있습니다.

- `+X`: launcher가 바라보는 정면 방향, 스크린 방향
- `+Y`: 테이블 좌우 방향
- `+Z`: 위쪽

회의실에는 다음 구조물이 있습니다.

- 긴 회의 테이블
- 좌측 유리벽
- 우측 유리벽
- 정면 유리벽
- 정면 검은 스크린
- 이동 가능한 타겟 오브젝트
- 천장
- 천장 조명 패널
- 좌우 의자들
- 유리창 밖 풍경 패널

정면 스크린은 환경 구조물이고, 실제 조준 대상은 별도로 추가한 `target_object`입니다.

## 테이블 구현

테이블은 `long_table` body 안의 `long_table_top` 단일 상판으로 구현되어 있습니다.  
이전에는 중앙 줄과 가장자리가 위로 튀어나온 별도 geom이 있었지만, 현재는 제거되어 전체 상판이 평평합니다.

현재 테이블 material은 조명과 OpenCV 후처리를 거친 Aim Camera 화면에서 대략 `#C8A28D rgba(200, 162, 141, 1.00)`에 가깝게 보이도록 역보정되어 있습니다.

```xml
<material name="table_mat" rgba="0.43 0.273 0.18 1" reflectance="0"/>
<material name="table_edge_mat" rgba="0.43 0.273 0.18 1" reflectance="0"/>
```

`table_edge_mat`는 테이블 다리에도 사용되며, 상판과 같은 색으로 맞춰져 있습니다.

## 유리벽과 외부 풍경 색상

좌측, 우측, 정면 벽은 유리 패널과 프레임으로 구성되어 있습니다.  
유리 너머에는 별도 외부 풍경 패널이 배치되어 있습니다.

- `left_outside_view`
- `right_outside_view`
- `front_outside_view`

목표는 Aim Camera에서 유리창 너머 색이 `#6C8BAA rgba(108, 139, 170, 1.00)`처럼 보이도록 하는 것입니다.  
조명과 OpenCV 후처리 때문에 XML 원색은 목표색보다 어둡고 덜 파랗게 설정되어 있습니다.

```xml
<texture type="skybox" name="skybox" builtin="gradient" rgb1="0.22 0.27 0.25" rgb2="0.22 0.27 0.25"/>
<material name="glass_mat" rgba="0.12 0.16 0.14 0.28" reflectance="0.02"/>
<material name="outside_view_mat" rgba="0.22 0.27 0.25 1" reflectance="0"/>
```

최근 샘플 기준 Aim Camera에서의 대략적인 화면상 색은 다음 정도입니다.

```text
target RGB: [108, 139, 170]
left:       [115.0, 144.7, 168.9]
right:      [100.5, 139.5, 159.2]
front:      [111.4, 137.7, 173.7]
```

## Launcher 배치

launcher는 회의 테이블의 `-X` 끝 중앙, `y=0` 위치에 배치되어 있습니다.  
포신 로컬 `+X` 방향이 월드 `+X` 방향, 즉 정면 스크린 방향을 향합니다.

반드시 유지되는 주요 이름은 다음과 같습니다.

- `yaw_joint`
- `pitch_joint`
- `yaw_motor`
- `pitch_motor`
- `rubber_projectile`
- `muzzle_site`
- `aim_camera`

발사대 본체 geom은 `launcher_visual` class를 사용하며 내부 충돌이 꺼져 있습니다.

```xml
<default class="launcher_visual">
  <geom contype="0" conaffinity="0"/>
</default>
```

이 설정은 발사대 본체끼리 충돌해서 yaw 회전이 막히는 문제를 방지하기 위한 것입니다.

## 타겟 오브젝트

타겟은 `conference_room_with_launcher.xml`의 `target_object` body로 구현되어 있습니다.  
물리적으로 떨어지거나 넘어지지 않도록 `mocap="true"` body로 만들었고, Python에서 `data.mocap_pos`를 수정해 위치를 이동합니다.
타겟 geom은 고무줄과 충돌할 수 있도록 collision을 끄지 않았습니다.

초기 위치:

```xml
<body name="target_object" mocap="true" pos="-1.20 0 0.805">
```

타겟은 카메라를 향하는 얇은 `Y-Z` 평면 형태입니다.  
기준 규격은 아래 값이지만, 현재 시뮬레이션에서는 카메라에서 잘 보이도록 전체 크기를 `1.8배` 확대했습니다.  
추가로 원과 아래 직사각형을 잇는 세로 막대는 시각적으로 더 길어 보이도록 기준 비율보다 조금 길게 조정되어 있습니다.

- 기준 아래 직사각형: `5cm x 2cm`
- 기준 숟가락형 전체 높이: 직사각형 위에서 원 윗부분까지 `6cm`
- 기준 위 원 지름: `4cm`
- 기준 막대 가로폭: `1.5cm`
- 현재 확대 후 아래 직사각형: `9cm x 3.6cm`
- 현재 확대 후 위 원 지름: `7.2cm`
- 현재 확대 후 막대 폭: `2.7cm`
- 현재 두께: 약 `1.08cm`

구현 geom:

- `target_base_rect`: 아래 직사각형
- `target_stem`: 세로 막대, 원과 직사각형 사이가 더 길어 보이도록 조정됨
- `target_round_head`: 위쪽 원형 머리, 지름 4cm sphere

타겟 색상은 Aim Camera 후처리까지 거친 화면에서 `#7A4F46 rgba(122, 79, 70, 1.00)`에 가깝게 보이도록 역보정되어 있습니다.

```xml
<material name="target_mat" rgba="0.392 0.181 0.117 1" reflectance="0"/>
```

최근 샘플 기준 화면상 타겟 평균색:

```text
target RGB: [122, 79, 70]
actual RGB: [120.6, 77.0, 69.2]
```

현재 XML 치수:

```xml
<geom name="target_base_rect" type="box" pos="0 0 0" size="0.0054 0.045 0.018"/>
<geom name="target_stem" type="box" pos="0 0 0.054" size="0.0054 0.0135 0.036"/>
<geom name="target_round_head" type="sphere" pos="0 0 0.108" size="0.036"/>
```

## 서보모터 구조

현재 actuator는 2개만 사용합니다.

| actuator | joint | 역할 |
| --- | --- | --- |
| `yaw_motor` | `yaw_joint` | 좌우 조향 |
| `pitch_motor` | `pitch_joint` | 상하 조향 |

`trigger_joint`, `trigger_motor`, trigger actuator는 없습니다.  
발사는 서보모터가 아니라 Python의 `do_fire()`에서 직접 처리합니다.

각도 제한은 두지 않았습니다.

- `yaw_joint`, `pitch_joint`: `range` 없음
- `yaw_motor`, `pitch_motor`: `ctrlrange` 없음

현재 키 한 번당 조향 단위는 1도입니다.

```python
YAW_STEP = np.deg2rad(1)
PITCH_STEP = np.deg2rad(1)
```

## 조작법

모든 키 입력은 OpenCV `Controls` 창에서 받습니다.

| 키 | 기능 |
| --- | --- |
| `W` | pitch 위로 1도 |
| `S` | pitch 아래로 1도 |
| `A` | yaw 왼쪽으로 1도 |
| `D` | yaw 오른쪽으로 1도 |
| `Space` | 고무줄 발사 |
| `P` | Aim Camera 창 켜기/끄기 |
| `Esc` | 종료 |
| `F` | 타겟을 화면 기준 왼쪽, 월드 `+Y` 방향으로 이동 |
| `H` | 타겟을 화면 기준 오른쪽, 월드 `-Y` 방향으로 이동 |
| `T` | 타겟을 스크린 방향, 월드 `+X` 방향으로 이동 |
| `G` | 타겟을 launcher 방향, 월드 `-X` 방향으로 이동 |
| `I` | MuJoCo viewer lookat을 `+X`로 이동 |
| `K` | MuJoCo viewer lookat을 `-X`로 이동 |
| `J` | MuJoCo viewer lookat을 `+Y`로 이동 |
| `L` | MuJoCo viewer lookat을 `-Y`로 이동 |

viewer 이동 step은 다음 값입니다.

```python
VIEW_MOVE_STEP = 0.20
```

타겟 이동 step은 다음 값입니다.

```python
TARGET_MOVE_STEP = 0.01
```

MuJoCo viewer에는 프로젝트 키를 직접 바인딩하지 않습니다.  
viewer의 마우스 회전, 줌, 기본 시각화 기능은 그대로 사용할 수 있습니다.

## Aim Camera

`aim_camera`는 포신 근처에 달린 장치 카메라입니다.

```xml
<camera name="aim_camera" pos="0.30 0 -0.13" xyaxes="0 -1 0  0 0 1" fovy="76"/>
```

MuJoCo 카메라는 로컬 `-Z` 방향을 보기 때문에 `xyaxes`를 조정해 포신 로컬 `+X` 방향을 보도록 했습니다.  
카메라 화면에는 테이블, 스크린, 좌우 유리벽과 의자들이 보이도록 설정되어 있습니다.

카메라 렌더 설정은 다음 구조를 유지합니다.

```python
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
TARGET_FPS = 30
```

한때 `2592 x 1944`로 올렸지만 현재 환경에서 `P` 입력 시 UI가 불안정해져 원래 사양인 `640 x 480`으로 되돌렸습니다.  
`Controls` 창이 먼저 뜨도록 하고, Aim Camera용 MuJoCo renderer는 `P`를 눌러 카메라가 켜질 때 지연 생성합니다.

Aim Camera 영상에는 OpenCV 후처리가 적용됩니다.

```python
CAMERA_EXPOSURE = 0.96
CAMERA_BRIGHTNESS = 2.0
BLOOM_THRESHOLD = 210
```

후처리는 원본 웹캠 같은 차가운 색감, 약한 bloom, 약한 blur를 만들기 위한 것입니다.

## 고무줄 발사 구조

고무줄은 `rubber_projectile` body입니다.

- `freejoint`를 가진 자유 물체
- 4개의 capsule geom으로 고무줄 형태를 근사
- material은 노란색
- 같은 body를 반복 재사용

`Space`를 누르면 `do_fire()`가 실행됩니다.

발사 순서:

1. 현재 `muzzle_site` 위치와 포신 방향을 계산합니다.
2. `rubber_projectile`을 포구 위치로 재배치합니다.
3. 회전 quaternion을 초기화합니다.
4. 포신 방향으로 초기 선속도를 부여합니다.
5. 발사 횟수 `fire_count`를 증가시킵니다.

발사 속도:

```python
LAUNCH_SPEED = 12.0
```

`R` 재장전 키는 없습니다.  
`Space`를 누를 때마다 자동으로 포구에 재배치한 뒤 다시 발사합니다.

## 고무줄 튕김 제어

고무줄은 첫 접촉 후 한 번만 약하게 튀고, 두 번째 접촉부터 멈추도록 제어합니다.

회의실 월드에서 착지면은 다음 geom입니다.

- `floor`
- `long_table_top`

첫 번째 접촉 시 속도 감쇠값:

```python
FIRST_BOUNCE_HORIZONTAL_SCALE = 0.65
FIRST_BOUNCE_VERTICAL_SCALE = 0.25
FIRST_BOUNCE_ANGULAR_SCALE = 0.25
```

두 번째 착지 접촉부터는 `qvel`을 0으로 고정해 여러 번 튀지 않게 합니다.

## 스레드 구조

`view_world.py`는 두 흐름으로 동작합니다.

### OpenCV UI 스레드

`ui_thread_fn()`이 별도 daemon thread로 실행됩니다.

담당 기능:

- `Controls` 창 표시
- 키 입력 처리
- yaw/pitch/view 좌표/target 좌표/fire_count 표시
- `P` 상태에 따라 Aim Camera 렌더링
- Aim Camera HUD 오버레이 표시

### MuJoCo 메인 루프

메인 스레드는 `mujoco.viewer.launch_passive(model, data)`로 viewer를 실행합니다.

담당 기능:

- MuJoCo simulation step
- viewer 화면 동기화
- viewer lookat 이동 반영
- 고무줄 튕김 제한 업데이트

`model`과 `data`는 두 스레드가 공유하므로 `threading.RLock()`으로 접근을 보호합니다.

## 현재 검증된 내용

최근 작업 중 확인한 항목은 다음과 같습니다.

- `conference_room_with_launcher.xml` 로드 정상
- `view_world.py`, `test.py` 문법 검사 통과
- actuator는 `yaw_motor`, `pitch_motor` 2개만 존재
- 포신 방향과 aim camera 방향이 월드 `+X`로 정렬
- 초기 내부 접촉이 yaw를 막지 않음
- 테이블 상판은 평평한 단일 geom
- 타겟 오브젝트는 실제 규격 기반의 mocap body로 구현됨
- 타겟 이동은 `F/H`로 좌우, `T/G`로 launcher-스크린 방향 이동
- trigger 관련 조인트/액추에이터 없음
- OpenCV `Controls` 창에서 모든 프로젝트 키 입력 처리

## 작업 시 주의점

- MuJoCo viewer에 프로젝트 키 입력을 직접 연결하지 않는 구조를 유지해야 합니다.
- `trigger_joint`, `trigger_motor`를 다시 만들지 않아야 합니다.
- 타겟은 현재 `target_object` 하나만 사용합니다. 불필요한 target body/site를 추가로 만들지 않는 편이 좋습니다.
- 발사 구조는 현재처럼 `Space` 입력 시 `rubber_projectile`을 재배치하고 초기 속도를 주는 방식입니다.
- 회의실 색상은 XML 원색이 아니라 Aim Camera 후처리와 조명을 거친 화면상 색을 기준으로 보정되어 있습니다.
