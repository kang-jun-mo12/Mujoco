# 프로젝트 워크플로우

이 문서는 MuJoCo 고무줄 발사대 프로젝트에서 지금까지 한 작업과 다음에 해야 할 작업을 정리한 문서입니다.

## 1. 완료된 작업

### 1.1 기본 발사대

- MuJoCo XML로 고무줄 발사대 구조를 구현했습니다.
- yaw/pitch 2축 구조를 사용합니다.
- actuator는 `yaw_motor`, `pitch_motor` 두 개만 사용합니다.
- `trigger_joint`, `trigger_motor`는 제거했습니다.
- `Space`를 누르면 `do_fire()`가 같은 `rubber_projectile`을 포구 위치로 재배치하고 발사합니다.
- `R` 재장전 기능은 삭제했습니다.
- 고무줄 색은 노란색으로 변경했습니다.

### 1.2 입력 구조

- 프로젝트 키 입력은 OpenCV `Controls` 창에서 받습니다.
- MuJoCo viewer는 보기 전용으로 유지합니다.
- viewer 기본 마우스 조작과 프로젝트 키 입력이 충돌하지 않게 했습니다.

### 1.3 회의실 월드

- 기존 발사대를 회의실 월드에 통합했습니다.
- 긴 테이블, 유리벽, 스크린, 천장 조명, 의자를 배치했습니다.
- 발사대는 테이블 `-X` 끝 중앙에 두고 `+X` 스크린 방향을 바라보게 했습니다.
- Aim Camera도 포신 방향과 정렬했습니다.

### 1.4 색감과 구조 보정

- 실제 회의실 사진과 비슷하게 조명과 색감을 조정했습니다.
- 테이블은 카메라 화면 기준 `#C8A28D`에 가깝게 보정했습니다.
- 유리창 너머 배경은 카메라 화면 기준 `#6C8BAA`에 가깝게 보정했습니다.
- 테이블 중앙/가장자리 돌출 구조를 제거하고 평평한 단일 상판으로 만들었습니다.

### 1.5 조작 기능

| 키 | 기능 |
| --- | --- |
| `W/S` | pitch 1도씩 조정 |
| `A/D` | yaw 1도씩 조정 |
| `Space` | 수동 발사 |
| `P` | Aim Camera 토글 |
| `O` | 반복 자동 조준 후 1회 발사 |
| `F/H` | 타겟 좌우 이동 |
| `T/G` | 타겟 앞뒤 이동 |
| `I/J/K/L` | viewer lookat 이동 |
| `Esc` | 종료 |

### 1.6 타겟 오브젝트

- 실제 타겟 사진을 참고해 아래 직사각형, 세로 막대, 위쪽 원형 머리 구조를 만들었습니다.
- 타겟은 `mocap` body라 Python에서 위치를 이동할 수 있습니다.
- 타겟 색은 Aim Camera 기준 `#7A4F46`에 가깝게 보정했습니다.
- 고무줄과 충돌할 수 있도록 target geom collision은 유지했습니다.

### 1.7 YOLO 검출

- 실제 환경 데이터로 학습한 YOLO ONNX 모델을 연결했습니다.
- 모델 파일은 `yolo_model/target_yolo11s_640_best.onnx`입니다.
- Aim Camera 프레임에서 target bbox를 검출합니다.
- Aim Camera 화면에는 bbox와 label/confidence만 표시합니다.
- 화면 중앙 에임포인트, bbox 중심점, 노란 연결선, 하단 err 텍스트는 제거했습니다.
- Controls 창에는 YOLO 검출 상태와 중심 오차가 텍스트로 표시됩니다.

### 1.8 조준 데이터 수집

- `collect_aim_dataset.py`를 추가했습니다.
- 타겟을 테이블 grid 위치로 옮기며 hit yaw/pitch를 시뮬레이션으로 찾습니다.
- Aim Camera 렌더링 후 YOLO bbox를 기록합니다.
- label은 절대 서보값이 아니라 `delta_yaw`, `delta_pitch`입니다.

5cm 전체 테이블 데이터 수집 결과:

```text
파일: datasets/aim_training_data_5cm.csv
rows: 53207
크기: 약 18.64MB
수집 시간: 약 3시간 49분
```

`datasets/`는 GitHub에 올리지 않습니다.

### 1.9 조준 보정 모델

- `analyze_aim_dataset.py`로 데이터 품질 리포트를 만들었습니다.
- `train_aim_delta_model.py`로 ridge regression 모델을 학습했습니다.
- 공통 예측 코드는 `aim_delta_model.py`에 있습니다.
- 모델 파일은 `models/aim_delta_ridge_5cm.npz`입니다.

검증 성능:

```text
yaw RMSE: 0.834 deg
pitch RMSE: 1.090 deg
both axes within 1 deg: 64.28%
```

### 1.10 자동 조준과 발사

`O` 키를 누르면 다음 흐름이 실행됩니다.

```text
Aim Camera 렌더링
-> YOLO target 검출
-> bbox feature 생성
-> delta_yaw / delta_pitch 예측
-> yaw/pitch 적용
-> 조향 안정화
-> 최대 6회 반복
-> 최종 target 검출이 있으면 do_fire()로 1회 발사
```

타겟이 검출되지 않으면 발사하지 않습니다. `Space` 수동 발사 기능도 유지합니다.

### 1.11 명중 피드백

- 고무줄 geom과 타겟 geom이 contact되면 hit로 판정합니다.
- `hit_effect` mocap body가 충돌 위치로 이동합니다.
- `hit_particle_0` ~ `hit_particle_8` sphere가 퍼지는 파티클 효과를 냅니다.
- Aim Camera 화면에는 `HIT! #n`이 표시됩니다.
- Controls 창에는 누적 hit count가 표시됩니다.

### 1.12 GitHub 배포 상태

GitHub에는 실행과 시연에 필요한 코드, XML, YOLO ONNX 모델, 학습된 조준 보정 모델이 올라가 있습니다.

포함되는 핵심 파일:

- `conference_room_with_launcher.xml`
- `view_world.py`
- `aim_delta_model.py`
- `models/aim_delta_ridge_5cm.npz`
- `yolo_model/target_yolo11s_640_best.onnx`
- `requirements.txt`

포함하지 않는 생성 데이터:

- `datasets/aim_training_data_5cm.csv`
- `logs/`
- `.venv/`
- `MUJOCO_LOG.TXT`

새 노트북에서 클론하면 시뮬레이션 실행, YOLO 검출, `O` 자동 조준/발사는 가능합니다. 데이터 재학습은 `datasets/aim_training_data_5cm.csv`를 별도로 복사해야 합니다.

## 2. 현재 프로젝트 상태

현재 프로젝트는 다음까지 가능한 상태입니다.

```text
MuJoCo 회의실 실행
-> Aim Camera 표시
-> YOLO target 검출
-> O 키 자동 조준 보정
-> 고무줄 1회 자동 발사
-> 타겟 명중 시 파티클/HIT 표시
```

## 3. 남은 문제와 개선 포인트

### 3.1 실제 명중률 평가

현재 모델은 검증 데이터 기준으로는 동작하지만, 실제 시뮬레이션에서 `O` 자동 발사 후 어느 정도 맞는지 위치별 평가가 필요합니다.

확인할 항목:

- 가까운 위치와 먼 위치의 명중률 차이
- 좌우 끝 위치에서의 yaw 오차
- pitch 예측 실패 사례
- YOLO bbox가 너무 작을 때의 실패
- hit 파티클이 실제 contact와 잘 맞는지

### 3.2 데이터 정제

5cm 데이터셋은 생성되었지만, 더 좋은 모델을 위해 정제가 필요할 수 있습니다.

- bbox confidence가 낮은 row 제거
- bbox 크기가 너무 작은 row 제거
- launcher 주변 또는 물리적으로 불안정한 위치 제외
- pitch/yaw delta 이상치 제거
- MuJoCo instability warning이 잦은 구간 확인

### 3.3 모델 개선

현재 모델은 ridge regression입니다. 더 높은 명중률이 필요하면 아래 모델을 검토합니다.

- RandomForestRegressor
- XGBoost 또는 LightGBM
- 작은 MLP
- 위치별 보정 테이블 + 회귀 모델 혼합
- 실제 자동 발사 결과를 다시 기록하는 closed-loop 보정 모델

### 3.4 자동 평가 루프

다음 단계로는 타겟 위치를 자동 순회하면서 `O` 자동 발사 결과를 기록하는 평가 스크립트를 만들 수 있습니다.

기록할 값:

- target 위치
- YOLO bbox
- 예측 delta_yaw / delta_pitch
- 최종 yaw / pitch
- 발사 여부
- hit 여부
- hit까지 걸린 시간

## 4. 다음 작업 추천 순서

1. 여러 타겟 위치에서 `O` 자동 조준/발사를 수동 테스트합니다.
2. hit 파티클과 `HIT!` 표시가 실제 명중 순간에 잘 뜨는지 확인합니다.
3. 자동 발사 성공/실패 사례를 기록합니다.
4. 실패 사례의 bbox, yaw/pitch, target 위치를 분석합니다.
5. 필요하면 데이터 필터 기준을 정하고 학습 CSV를 정제합니다.
6. ridge regression보다 강한 모델을 학습합니다.
7. 자동 평가 루프를 만들어 위치별 명중률을 CSV로 기록합니다.
8. 명중률이 충분하면 자동 순회 테스트와 실제 환경 비교로 확장합니다.

## 5. 장기 목표

최종 목표 흐름은 다음과 같습니다.

```text
Aim Camera 화면
-> YOLO 타겟 검출
-> bbox feature 추출
-> 조준 보정 모델
-> yaw/pitch 자동 이동
-> 고무줄 발사
-> hit 여부 확인
-> 결과 기록
-> 모델 개선
```

이 흐름이 완성되면 실제 환경에서 학습한 YOLO 모델을 MuJoCo 가상환경에 적용하고, 시뮬레이션에서 자동 조준/발사 정책을 개선하는 실험 플랫폼이 됩니다.
