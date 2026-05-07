# 프로젝트 워크플로우

이 문서는 지금까지 진행한 작업과 다음에 해야 할 작업을 한눈에 보기 위한 작업 흐름 정리입니다.

## 1. 지금까지 완료한 작업

### 1.1 기본 고무줄 발사대 구현

- MuJoCo XML로 고무줄 발사대 구조를 구현했습니다.
- 발사대는 yaw/pitch 2축으로 움직입니다.
- actuator는 `yaw_motor`, `pitch_motor` 두 개만 사용합니다.
- `trigger_joint`, `trigger_motor`는 제거했습니다.
- `Space`를 누르면 Python의 `do_fire()`에서 같은 `rubber_projectile`을 포구 위치로 재배치하고 초기 속도를 줘서 반복 발사합니다.
- `R` 재장전 기능은 삭제했습니다.
- 고무줄 색은 노란색으로 변경했습니다.

### 1.2 입력 구조 분리

- MuJoCo viewer와 프로젝트 키 입력이 충돌하지 않도록 키 입력을 OpenCV `Controls` 창에서 받도록 바꿨습니다.
- MuJoCo viewer는 마우스 회전, 이동, 확대/축소 등 보기 전용으로 유지합니다.
- `P` 키로 Aim Camera 창을 켜고 끌 수 있습니다.

### 1.3 회의실 월드 제작

- 기존 발사대를 회의실 월드 안에 통합했습니다.
- 긴 회의 테이블, 유리벽, 정면 스크린, 천장 조명, 의자를 배치했습니다.
- 발사대는 테이블의 `-X` 끝 중앙에 놓고, 스크린 방향인 `+X`를 바라보게 했습니다.
- Aim Camera도 포신 방향과 같은 `+X` 방향을 보도록 정렬했습니다.

### 1.4 사진과 비슷한 색감 보정

- Aim Camera 화면이 실제 회의실 사진과 비슷해지도록 조명과 색감을 조정했습니다.
- 테이블 색은 카메라 화면 기준 `#C8A28D`에 가깝게 보정했습니다.
- 좌우/정면 유리창 너머 배경은 카메라 화면 기준 `#6C8BAA`에 가깝게 보정했습니다.
- 테이블 중앙선과 가장자리 돌출 구조를 제거해 평평한 단일 상판으로 만들었습니다.

### 1.5 조작 기능 확장

- `W/S`: pitch 1도씩 조정
- `A/D`: yaw 1도씩 조정
- `Space`: 발사
- `P`: Aim Camera 토글
- `F/H`: 타겟 좌우 이동
- `T/G`: 타겟을 스크린/발사대 방향으로 이동
- `I/J/K/L`: MuJoCo viewer의 전지적 시점 lookat 이동
- `Esc`: 종료

### 1.6 타겟 오브젝트 제작

- 실제 타겟 사진을 기준으로 아래 직사각형, 세로 막대, 위쪽 원형 머리 구조를 만들었습니다.
- 위쪽은 직사각형이 아니라 원형 머리로 수정했습니다.
- 타겟은 Aim Camera에서 잘 보이도록 원래 규격보다 약간 크게 조정했습니다.
- 타겟 색은 Aim Camera 기준 `#7A4F46`에 가깝게 보정했습니다.
- 타겟은 `mocap` body로 구현해 Python에서 위치를 움직일 수 있게 했습니다.

### 1.7 YOLO 모델 연결

- 실제 환경 데이터로 학습된 YOLO 모델을 프로젝트에 추가했습니다.
- OpenCV DNN으로 `target_yolo11s_640_best.onnx`를 로드합니다.
- Aim Camera 프레임에서 타겟 bbox를 검출합니다.
- Aim Camera 창에 bbox, confidence, 중심점, 화면 중심 기준 오차를 overlay로 표시합니다.
- Controls 창에도 YOLO 검출 상태를 표시합니다.

### 1.8 조준 데이터 수집 스크립트 추가

- `collect_aim_dataset.py`를 추가했습니다.
- 타겟을 테이블 위 grid 위치로 옮기고, 해당 위치를 맞출 수 있는 yaw/pitch를 MuJoCo 발사 시뮬레이션으로 찾습니다.
- 각 위치에서 Aim Camera를 렌더링하고 YOLO bbox를 검출합니다.
- 절대 서보모터 값이 아니라 현재 포신 방향 기준 보정량인 `delta_yaw`, `delta_pitch`를 CSV label로 저장합니다.

### 1.9 5cm 전체 테이블 데이터 수집 완료

- 전체 테이블 범위 `x=-3.0~4.2`, `y=-0.9~0.9`를 `5cm` 간격으로 수집했습니다.
- X 범위를 4개 part로 나누어 병렬 실행했습니다.
- 최종 병합 파일은 `datasets/aim_training_data_5cm.csv`입니다.
- 최종 데이터 row는 `53207`개입니다.
- 수집 시간은 약 `3시간 49분`이 걸렸습니다.
- `datasets/` 폴더는 생성 데이터이므로 GitHub에는 올리지 않도록 `.gitignore`에 포함되어 있습니다.

### 1.10 조준 보정 모델 학습 및 연결

- `analyze_aim_dataset.py`로 5cm 데이터셋 품질 리포트를 생성했습니다.
- `train_aim_delta_model.py`로 ridge regression 기반 조준 보정 모델을 학습했습니다.
- 모델 파일은 `models/aim_delta_ridge_5cm.npz`입니다.
- 검증 성능은 yaw RMSE 약 `0.834도`, pitch RMSE 약 `1.090도`입니다.
- `view_world.py`에 `O` 키를 추가해 최신 YOLO bbox 기준 반복 자동 보정을 적용한 뒤 1회 발사할 수 있게 했습니다.

### 1.11 명중 시각 효과 추가

- 고무줄 geom과 타겟 geom이 contact되면 hit로 판정합니다.
- hit 순간 `hit_effect` mocap body가 충돌 위치로 이동합니다.
- `hit_particle_0` ~ `hit_particle_8` sphere가 짧게 퍼지며 파티클 효과를 냅니다.
- Aim Camera 화면에는 `HIT!` 텍스트가 잠깐 표시됩니다.
- Controls 창에는 누적 hit count가 표시됩니다.

## 2. 현재 프로젝트 상태

현재 프로젝트는 수동 조작, YOLO 타겟 검출, 자동 데이터 수집의 기반이 모두 연결된 상태입니다.

사용자는 `view_world.py`를 실행해서 회의실 안의 고무줄 발사대를 직접 조작할 수 있습니다.  
`P`를 누르면 포신에 달린 Aim Camera 화면이 뜨고, YOLO가 타겟을 검출합니다.  
`collect_aim_dataset.py`를 실행하면 여러 타겟 위치와 여러 현재 조준 상태에 대해 자동 조준 학습용 CSV를 만들 수 있습니다.  
현재는 5cm 간격 전체 테이블 데이터셋이 로컬 `datasets/aim_training_data_5cm.csv`에 생성되어 있고, 첫 조준 보정 모델이 `models/aim_delta_ridge_5cm.npz`에 저장되어 있습니다.

## 3. 현재 남은 핵심 문제

### 3.1 데이터 품질 확인

5cm 전체 테이블 데이터는 생성되었지만, 바로 학습에 넣기 전에 품질 확인이 필요합니다.

확인할 항목:

- bbox가 너무 작거나 confidence가 낮은 row
- launcher와 너무 가까운 위치의 이상치
- `delta_yaw`, `delta_pitch`가 과하게 큰 row
- 같은 타겟 위치에서 검출이 불안정한 row
- 명중 각도 탐색 중 MuJoCo instability warning이 잦았던 구간

### 3.2 발사대와 너무 가까운 영역 처리

전체 테이블을 수집하면 발사대와 타겟이 너무 가까워지거나 겹치는 위치가 생길 수 있습니다.  
이 영역은 학습 데이터에서 제외하거나, 스크립트에 launcher 주변 제외 옵션을 추가하는 것이 좋습니다.

### 3.3 데이터 수집 속도 개선

현재 Ryzen 5 3500 기준 위치 1개당 약 `6.4초` 정도가 걸렸습니다.  
10cm 간격 전체 테이블은 약 `2시간 28분` 정도로 예상됩니다.

속도를 줄이는 방법:

- X 범위를 여러 구간으로 나눠 병렬 실행
- YOLO 추론을 GPU/ONNX Runtime/TensorRT로 변경
- search 범위와 step 최적화
- 이미 계산한 위치의 hit angle 캐싱

### 3.4 조준 회귀 모델 개선

현재 첫 모델은 ridge regression입니다. 다음 feature를 입력으로 사용합니다.

- bbox 중심 위치
- bbox 크기
- bbox 면적
- 화면 중심 대비 bbox 중심 오차
- 현재 yaw/pitch

예측 label:

- `delta_yaw`
- `delta_pitch`

개선 후보:

- RandomForestRegressor
- XGBoost 또는 LightGBM
- 작은 MLP
- 현재 예측 후 실제 발사 명중 여부를 다시 데이터로 기록하는 보정 루프

### 3.5 자동 조준/발사 연결

학습 모델이 준비되면 `view_world.py`에 자동 모드를 추가합니다.

예상 흐름:

1. Aim Camera 프레임 렌더링
2. YOLO로 타겟 bbox 검출
3. bbox feature 생성
4. 회귀 모델로 `delta_yaw`, `delta_pitch` 예측
5. 현재 yaw/pitch에 보정량 적용
6. 짧게 안정화
7. `do_fire()` 실행

## 4. 다음 작업 추천 순서

1. `view_world.py`에서 `P`로 Aim Camera를 켜고 YOLO 검출을 확인합니다.
2. `O` 키로 반복 자동 보정과 1회 발사를 실행해 실제 명중률과 hit 효과를 확인합니다.
3. 여러 위치에서 예측 보정 후 명중/실패를 기록합니다.
4. launcher 주변 제외 기준과 이상치 제거 기준을 정합니다.
5. 필요하면 정제된 학습 CSV를 새로 저장합니다.
6. ridge regression보다 강한 모델을 학습합니다.
7. 자동 발사가 안정되면 여러 타겟 위치를 자동 순회하며 명중률을 기록하는 평가 루프를 추가합니다.
8. 실제 데이터와 MuJoCo 데이터 간 차이를 비교합니다.
9. 필요하면 MuJoCo 월드 색감, 타겟 크기, 카메라 후처리를 더 조정합니다.

## 5. 장기 목표

최종적으로 만들고 싶은 구조는 다음과 같습니다.

```text
Aim Camera 화면
  -> YOLO 타겟 검출
  -> bbox feature 추출
  -> 조준 보정 모델
  -> yaw/pitch 자동 이동
  -> 고무줄 발사
  -> 타겟 명중 여부 확인
```

이 흐름이 완성되면 실제 환경에서 학습한 YOLO 모델이 MuJoCo 가상환경에서도 타겟을 검출하고, 시뮬레이션에서 조준 정책을 학습해 자동 발사까지 수행하는 프로젝트가 됩니다.
