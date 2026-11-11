# AI 파이프라인 실행·재현 가이드

KNHANES 데이터로 당뇨·고혈압 위험도 모델을 처음부터 다시 만들고, 서비스용 아티팩트까지 재현하는 절차입니다.
모든 명령은 `apps/ai`에서 실행합니다.

## 1. 준비

| 항목 | 내용 |
|---|---|
| 원시 데이터 | 국민건강영양조사 2020~2024 기초자료 `hn20_all.sas7bdat` ~ `hn24_all.sas7bdat` |
| 저장 위치 | `apps/ai/data/raw/knhanes/` (Git 제외) |
| 의존성 | `uv sync` (`uv.lock` 기준 버전 고정) |
| 산출물 위치 | `apps/ai/data/`, `apps/ai/artifacts/` (모두 Git 제외) |

## 2. 실행 순서

| 단계 | 명령 | 사용 데이터 | 주요 산출물 |
|---:|---|---|---|
| 1 | `uv run python -m src.pipelines.knhanes_data_pipeline` | 원시 데이터 | 병합·라벨·전처리·분할 데이터, 품질·라벨·분할 보고서 |
| 2 | `uv run python -m src.pipelines.knhanes_training_pipeline` | Train, Validation | Baseline 모델·비교 보고서 (`artifacts/reports/knhanes_baseline/`) |
| 3 | `uv run python -m src.pipelines.knhanes_tuning_pipeline` | Train(CV), Validation | 최종 모델·보정기·위험 등급 경계 (`artifacts/models/knhanes_tuned/`) |
| 4 | `uv run python -m src.pipelines.knhanes_final_evaluation_pipeline` | **Test (1회만)** | 최종 평가·SHAP 보고서 (`artifacts/reports/knhanes_final_evaluation/`) |
| 5 | `uv run python -m src.pipelines.knhanes_serving_bundle_pipeline` | Train(범위 기록), Validation(일치 확인) | 서빙 아티팩트 (`artifacts/models/knhanes_serving/`) |
| 6 | `uv run python -m src.pipelines.knhanes_reproducibility_pipeline` | Train, Validation | 재현성 보고서 (`artifacts/reports/knhanes_reproducibility/`) |

- 1단계는 병합 → 라벨 생성 → 전처리 → 검사값 전환·분할을 차례로 실행합니다.
- 3단계는 Optuna 탐색 때문에 수십 분이 걸립니다. 알고리즘별 시간 상한(`TUNING_TIMEOUT_SECONDS`)에 걸리면 완료된 trial 수가 달라질 수 있으므로, 결과 비교 시 보고서의 trial 수를 함께 확인합니다.
- 4단계는 보고서가 이미 있으면 실행을 거부합니다. 같은 Test로 다시 평가하지 않기 위함입니다.
- 이전 형식의 최종 평가 보고서에 경계별 혼동 행렬·F1을 보강할 때는 `--supplement-only`를 붙입니다. Test를 다시 읽지 않습니다.

## 3. 데이터 누수 방지 규칙

```text
연도·가구 단위 분할 (2024 = Test, 2022~2023 가구 일부 = Validation, 나머지 = Train. 최종 모델은 Train B: 2022~2023)
  ↓
규칙 기반 전처리만 분할 전 적용 (코드값 변환, BMI 계산, 고정 계수 검사값 전환: 학습하는 통계 없음)
  ↓
fit이 필요한 전처리는 Train(또는 CV 폴드의 학습 부분)에만 fit (결측 대치, 원-핫, 스케일러, SMOTE)
  ↓
Validation·Test에는 Train으로 fit한 전처리기로 transform만 적용
```

| 단계 | fit에 쓰는 데이터 | 평가·결정에 쓰는 데이터 |
|---|---|---|
| 하이퍼파라미터 튜닝 | Train CV 폴드의 학습 부분 | Train CV 폴드의 검증 부분 |
| 확률 보정 | Train OOF 확률 | Train OOF 확률 |
| 최종 모델 | Train 전체 | — |
| 위험 등급 경계 | — | 미진단자 Validation |
| 최종 평가 | — | Test (1회) |

## 4. 서빙 아티팩트 구조

```text
artifacts/models/knhanes_serving/
├── serving_manifest.json        모델별 폴더와 metadata.json 해시
├── diabetes_risk_model/
│   ├── model.pkl                학습된 분류기
│   ├── preprocessor.pkl         Train에만 fit한 전처리기
│   ├── calibrator.pkl           확률 보정기
│   ├── thresholds.json          위험 등급 경계와 산출 기준
│   └── metadata.json            출처·하이퍼파라미터·입력 스키마·학습 범위·버전·파일 해시
└── hypertension_risk_model/
    └── (같은 구성)
```

- **로드:** `load_serving_bundle()`이 매니페스트 → `metadata.json` → 각 파일 순서로 SHA-256을 확인한 뒤에만 pickle을 엽니다.
- **추론:** `KnhanesRiskPredictor`가 같은 전처리기·보정기·경계를 그대로 적용합니다. 규칙 기반 전처리(`KnhanesPreprocessor`)는 학습한 상태가 없으므로 코드로 적용합니다.
- **출처 추적:** `metadata.json`에 원 모델 해시(최종 평가 보고서와 대조), 학습 데이터 해시, 코드 커밋, 라이브러리 버전이 기록됩니다.

## 5. 재현성 확인

6단계는 `metadata.json`의 기록만으로 처음부터 다시 학습해 다음을 비교합니다. 하나라도 다르면 오류로 종료합니다.

| 항목 | 기준 |
|---|---|
| 학습 데이터 | `X_train`, `y_train` 해시 일치 |
| 모델 | 같은 하이퍼파라미터로 학습한 모델의 Validation 원 확률 완전 일치 |
| 보정 | Train OOF로 다시 고른 보정 방법과 보정 확률 완전 일치 |
| 위험 등급 경계 | 미진단자 Validation으로 다시 산출한 경계 완전 일치 |

Optuna 탐색 자체는 다시 실행하지 않습니다. 탐색 결과(하이퍼파라미터)는 `metadata.json`과 튜닝 보고서에 기록되어 있습니다.

## 6. 다시 만들 때 주의할 점

- 4단계(Test 평가)를 다시 하려면 `artifacts/reports/knhanes_final_evaluation/`을 지워야 합니다. 이 경우 기존 Test 결과는 더 이상 깨끗한 평가가 아니므로 보고서에 그 사실을 남깁니다.
- 아티팩트는 커밋 후 생성해야 `metadata.json`의 `code_version.src_has_uncommitted_changes`가 `false`로 기록됩니다.
- 라이브러리 버전이 저장 시점과 다르면 로드 시 경고가 남습니다. `uv sync`로 `uv.lock` 버전을 맞춥니다.
