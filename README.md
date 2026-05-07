# MuJoCo Rubber Band Launcher

MuJoCo 회의실 환경 안에서 2축 고무줄 발사대를 조작하고, 포신에 달린 Aim Camera 화면에 YOLO 타겟 검출과 자동 조준/발사를 적용하는 프로젝트입니다.

## 프로젝트 목적

이 프로젝트의 핵심 목적은 **MuJoCo 내부에서 만든 가상 데이터로 YOLO를 학습하는 것**이 아닙니다.  
반대로, **실제 리얼월드에서 촬영한 타겟 이미지 데이터로 학습한 YOLO 모델이 MuJoCo 안에 최대한 유사하게 구현한 회의실/타겟 환경에서도 똑같이 추론되는지**를 확인하는 것입니다.

즉, 확인하려는 질문은 다음과 같습니다.

```text
실제 카메라로 찍은 데이터
-> 실제 데이터로 YOLO 타겟 검출 모델 학습
-> MuJoCo 안에 실제 회의실/테이블/타겟과 비슷한 환경 구현
-> MuJoCo Aim Camera 화면에 실제 카메라 같은 색감/밝기/blur 적용
-> 리얼월드 학습 YOLO를 MuJoCo 화면에 그대로 적용
-> 가상환경에서도 타겟이 안정적으로 검출되는지 확인
-> 검출된 bbox로 고무줄 발사대가 자동 조준/발사할 수 있는지 실험
```

이 프로젝트는 일종의 **real-to-sim perception transfer 실험**입니다.  
리얼월드에서 학습된 인식 모델이 시뮬레이션 환경으로 들어왔을 때 domain gap이 얼마나 작은지, 그리고 그 검출 결과를 실제 제어 문제인 조준/발사에 사용할 수 있는지를 확인합니다.

## 현재까지 확인된 성능

MuJoCo Aim Camera에서 수집한 5cm 간격 전체 테이블 데이터셋 기준:

```text
총 bbox/조준 데이터 row: 53207
YOLO confidence median: 0.6805
YOLO confidence p95: 0.8394
데이터가 생성된 target 위치 수: 4313
```

YOLO bbox를 이용해 `delta_yaw`, `delta_pitch`를 예측하는 ridge regression 조준 보정 모델의 검증 성능:

```text
yaw RMSE: 0.834 deg
pitch RMSE: 1.090 deg
both axes within 1 deg: 64.28%
```

현재는 `O` 키를 누르면 YOLO 검출 결과를 기반으로 반복 자동 조준을 수행하고, 최종 타겟이 검출되어 있으면 고무줄을 1회 발사합니다. 실제 명중률은 앞으로 여러 위치에서 자동 평가 루프로 더 정량화할 예정입니다.

## 현재 기능

- 회의실 월드와 긴 회의 테이블
- yaw/pitch 2축 고무줄 발사대
- OpenCV `Controls` 창 기반 키 입력
- MuJoCo viewer 보기 전용 유지
- Aim Camera OpenCV 화면
- 실제 환경 데이터로 학습한 YOLO ONNX 타겟 검출
- `O` 키 자동 조준 보정 후 고무줄 1회 발사
- 타겟 명중 시 파티클 효과와 `HIT!` 표시
- 5cm 간격 전체 테이블 조준 데이터셋 수집
- ridge regression 기반 조준 보정 모델

## 시스템 스펙 요약

| 항목 | 현재 값 |
| --- | --- |
| 시뮬레이터 | MuJoCo |
| 메인 실행 파일 | `view_world.py` |
| 메인 월드 XML | `conference_room_with_launcher.xml` |
| 입력 창 | OpenCV `Controls` |
| viewer 역할 | 보기 전용 |
| 발사대 축 | yaw / pitch 2축 |
| actuator | `yaw_motor`, `pitch_motor` |
| trigger actuator | 없음 |
| 수동 발사 | `Space` |
| 자동 조준/발사 | `O` |
| Aim Camera 해상도 | `640 x 480` |
| 목표 FPS | `30` |
| YOLO 입력 크기 | `640 x 640` letterbox |
| YOLO 모델 | `yolo_model/target_yolo11s_640_best.onnx` |
| 조준 보정 모델 | `models/aim_delta_ridge_5cm.npz` |
| 고무줄 발사 속도 | `LAUNCH_SPEED = 12.0` |
| 조향 step | `1 deg` |
| 타겟 이동 step | `0.01m` |
| viewer lookat 이동 step | `0.20m` |
| 테이블 크기 | `7.2m x 1.8m` |
| 전체 테이블 좌표 범위 | `x=-3.0~4.2`, `y=-0.9~0.9` |
| 5cm 데이터셋 row | `53207` |

## 실행

```powershell
cd C:\Users\DESKTOP\Desktop\mujoco
.\.venv\Scripts\python.exe view_world.py
```

OpenCV `Controls` 창에 포커스를 둔 상태에서 키를 입력해야 합니다.

## 조작법

| Key | Action |
| --- | --- |
| `W/S` | pitch 위/아래 1도 조정 |
| `A/D` | yaw 좌/우 1도 조정 |
| `Space` | 고무줄 수동 발사 |
| `P` | Aim Camera 켜기/끄기 |
| `O` | YOLO 검출 기반 반복 자동 조준 후 1회 발사 |
| `F/H` | 타겟 좌/우 이동 |
| `T/G` | 타겟을 스크린/발사대 방향으로 이동 |
| `I/J/K/L` | MuJoCo viewer lookat 이동 |
| `Esc` | 종료 |

## 자동 조준 테스트 흐름

```text
1. view_world.py 실행
2. Controls 창에 포커스
3. P 키로 Aim Camera 켜기
4. YOLO bbox가 타겟을 잡는지 확인
5. O 키 입력
6. 자동 조준 보정 후 고무줄 1회 발사
7. 맞으면 파티클 효과와 HIT! 표시 확인
```

## 전체 동작 파이프라인

```text
MuJoCo 회의실 월드 로드
-> 발사대와 타겟 배치
-> Aim Camera 렌더링
-> 실제 카메라 느낌의 후처리 적용
-> 리얼월드 데이터로 학습한 YOLO ONNX 모델 추론
-> target bbox 검출
-> bbox feature 생성
-> 조준 보정 모델이 delta_yaw / delta_pitch 예측
-> yaw/pitch motor control에 반영
-> 반복 보정
-> 고무줄 1회 발사
-> target contact 발생 시 hit 파티클 표시
```

## 주요 파일

| 파일 | 역할 |
| --- | --- |
| `conference_room_with_launcher.xml` | 회의실 월드, 발사대, 고무줄, 타겟, hit 파티클 효과 |
| `view_world.py` | 메인 실행, 조작, YOLO 추론, 자동 조준/발사 |
| `aim_delta_model.py` | 조준 보정 모델 로드/예측 공통 코드 |
| `models/aim_delta_ridge_5cm.npz` | 학습된 조준 보정 모델 |
| `collect_aim_dataset.py` | 조준 학습용 CSV 수집 |
| `analyze_aim_dataset.py` | 수집 데이터 품질 리포트 생성 |
| `train_aim_delta_model.py` | ridge regression 조준 보정 모델 학습 |
| `reports/aim_dataset_quality_5cm.md` | 5cm 데이터셋 품질 리포트 |
| `reports/aim_delta_model_5cm.md` | 조준 보정 모델 성능 리포트 |
| `yolo_model/target_yolo11s_640_best.onnx` | Aim Camera용 YOLO 타겟 검출 모델 |
| `progress_summary.md` | 프로젝트 전체 설명 |
| `project_workflow.md` | 진행 작업과 다음 작업 흐름 |

## 데이터셋

5cm 간격 전체 테이블 데이터셋은 로컬에 생성되어 있습니다.

```text
datasets/aim_training_data_5cm.csv
```

이 파일은 약 18.64MB이고 생성 데이터이므로 GitHub에는 올리지 않습니다.  
시뮬레이션 실행과 `O` 자동 조준/발사는 이미 학습된 `models/aim_delta_ridge_5cm.npz`를 사용하므로 데이터셋 CSV가 없어도 동작합니다.

## 회의실 월드 스펙

좌표계:

| 축 | 의미 |
| --- | --- |
| `+X` | 발사대 정면, 스크린 방향 |
| `+Y` | 테이블 좌우 방향 |
| `+Z` | 위쪽 |

테이블:

```text
body: long_table
geom: long_table_top
형태: box
실제 크기: 7.2m x 1.8m
상판 높이: 약 0.75m
색상 목표: Aim Camera 기준 #C8A28D
구조: 중앙/가장자리 돌출 없는 평평한 단일 상판
```

유리벽과 배경:

```text
왼쪽/오른쪽/정면 벽: 유리 패널 구조
외부 배경 목표색: Aim Camera 기준 #6C8BAA
정면: 검은 스크린 포함
```

타겟:

```text
body: target_object
타입: mocap body
초기 위치: x=-1.20, y=0, z=0.805
형태: 아래 직사각형 + 세로 막대 + 위쪽 원형 머리
색상 목표: Aim Camera 기준 #7A4F46
이동 키: F/H/T/G
```

발사대:

```text
base 위치: 테이블 -X 끝 중앙
방향: 월드 +X, 스크린 방향
관절: yaw_joint, pitch_joint
모터: yaw_motor, pitch_motor
포구 site: muzzle_site
카메라: aim_camera
내부 충돌: launcher visual geom은 collision off
```

고무줄:

```text
body: rubber_projectile
joint: freejoint
geom: rb_1, rb_2, rb_3, rb_4 capsule
색상: 노란색
발사 방식: 같은 body를 muzzle_site로 재배치 후 포신 방향 속도 부여
재장전 키: 없음
반복 발사: Space 또는 O 동작마다 자동 재배치
```

명중 효과:

```text
명중 판정: rb_1~rb_4와 target_base_rect / target_stem / target_round_head contact
효과 body: hit_effect
파티클 geom: hit_particle_0 ~ hit_particle_8
표시: MuJoCo 월드 파티클 + Aim Camera HIT! 텍스트 + Controls hit count
```

## YOLO 추론 방법

이 프로젝트에서 사용하는 YOLO 모델은 MuJoCo 이미지로 학습한 모델이 아니라, 실제 환경에서 촬영한 타겟 데이터로 학습한 모델입니다.

MuJoCo에서 추론할 때는 다음 방식으로 real-world 카메라와의 차이를 줄였습니다.

1. 회의실 구조, 테이블 색, 유리벽 색, 타겟 색을 실제 사진에 가깝게 조정했습니다.
2. Aim Camera를 포신에 부착하고 실제 카메라처럼 낮은 시점에서 테이블과 스크린을 보게 했습니다.
3. MuJoCo 렌더링 이미지에 색감, 밝기, bloom, blur 후처리를 적용했습니다.
4. YOLO 입력 크기와 동일하게 `640 x 640` letterbox 전처리를 적용했습니다.
5. ONNX 모델을 OpenCV DNN으로 실행했습니다.

현재 Aim Camera 화면에는 bbox와 label/confidence만 표시합니다. 화면 중앙 에임포인트, bbox 중심점, 노란 연결선, 하단 err 텍스트는 제거했습니다. 다만 자동조준 계산을 위해 bbox 중심 오차는 내부적으로 계속 계산합니다.

## 자동 조준/발사 방법

### Ridge regression 모델이란?

Ridge regression은 **선형 회귀에 과적합을 줄이는 규제를 추가한 모델**입니다.  
일반 선형 회귀는 입력 feature에 가중치를 곱해 출력값을 예측합니다.

```text
예측값 = w1*x1 + w2*x2 + w3*x3 + ... + b
```

Ridge regression은 여기에 `가중치가 너무 커지지 않도록 하는 벌점`을 추가합니다.  
그래서 데이터의 우연한 노이즈를 과하게 외우는 것을 줄이고, 예측이 더 안정적으로 나오게 합니다.

이 프로젝트에서는 ridge regression을 다음 역할로 사용합니다.

```text
입력:
YOLO bbox 중심 오차, bbox 크기, bbox 면적, confidence, 현재 yaw/pitch

출력:
현재 포신 방향에서 타겟을 맞추기 위해 더 움직여야 하는 delta_yaw, delta_pitch
```

즉 이 모델은 절대적인 서보모터 각도를 바로 맞히는 모델이 아니라, **현재 Aim Camera 화면과 현재 포신 각도에서 얼마나 더 보정해야 하는지**를 예측하는 모델입니다.

이 구조를 선택한 이유는 Aim Camera가 포신에 붙어 있기 때문입니다. 포신이 움직이면 카메라 화면도 같이 바뀌므로, 고정된 목표 각도보다 현재 화면 기준 보정량을 예측하는 편이 더 자연스럽습니다.

현재 모델은 완전한 직선 관계만 쓰지 않고, 입력 feature의 2차항과 feature끼리의 곱도 함께 사용합니다. 그래서 bbox 크기나 현재 각도에 따라 달라지는 곡선적인 관계도 어느 정도 표현할 수 있습니다.

`O` 키를 누르면 다음 절차가 실행됩니다.

```text
1. Aim Camera 현재 프레임 렌더링
2. YOLO로 target bbox 검출
3. bbox 중심/크기/confidence와 현재 yaw/pitch로 feature 생성
4. ridge regression 모델로 delta_yaw, delta_pitch 예측
5. yaw_motor, pitch_motor target에 반영
6. MuJoCo step을 조금 진행해 조향 안정화
7. 최대 6회 반복
8. 마지막에도 target이 검출되면 do_fire()로 1회 발사
9. target contact가 생기면 hit 효과 표시
```

타겟이 검출되지 않으면 발사하지 않습니다. `Space` 수동 발사 기능은 별도로 유지됩니다.

## 데이터 분석과 모델 재학습

로컬에 `datasets/aim_training_data_5cm.csv`가 있을 때 실행합니다.

```powershell
.\.venv\Scripts\python.exe analyze_aim_dataset.py
.\.venv\Scripts\python.exe train_aim_delta_model.py
```

## 새 노트북에서 클론 후 실행

```powershell
git clone https://github.com/kang-jun-mo12/Mujoco.git
cd Mujoco
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe view_world.py
```

클론한 노트북에서도 시뮬레이션 실행, YOLO 검출, `O` 자동 조준/발사는 가능합니다.  
다만 `datasets/aim_training_data_5cm.csv`는 GitHub에 없으므로 재학습이나 데이터 분석을 하려면 따로 복사해야 합니다.
