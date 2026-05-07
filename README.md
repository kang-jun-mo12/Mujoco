# MuJoCo Rubber Band Launcher

MuJoCo 회의실 환경 안에서 2축 고무줄 발사대를 조작하고, 포신에 달린 Aim Camera 화면에 YOLO 타겟 검출과 자동 조준/발사를 적용하는 프로젝트입니다.

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
