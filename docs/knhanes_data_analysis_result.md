# Phase 1: 데이터 로드 및 탐색 (EDA) 결과 보고서 (DataAnalyzer 활용)

## 1. 데이터 개요
- **데이터 소스**: `apps/ai/data/processed/knhanes/knhanes_processed.parquet`
- **데이터 크기**: 15,497 행 (전처리 완료 데이터)
- **주요 타겟 변수**: `diabetes_prevalence` (당뇨 유병), `hypertension_prevalence` (고혈압 유병)
- **분석 도구**: `apps/ai/core/utils/data_analyzer.py` (`DataAnalyzer`)

## 2. 상관관계 분석 결과 (Top 20)

`DataAnalyzer`를 통해 범주형 변수를 포함한 전체 변수와 타겟 간의 상관관계를 분석하였습니다.

### 2.1. 당뇨병 (diabetes_prevalence) 상관관계
1. `has_diabetes_diagnosis`: 0.98
2. `hba1c` (당화혈색소): 0.59
3. `has_hypertension_diagnosis`: 0.50
4. `fbs` (공복혈당): 0.49
5. `hypertension_prevalence`: 0.42
6. `urine_glucose` (요당): 0.39
7. `family_history_diabetes`: 0.26
8. `total_cholesterol`: 0.25
9. `ldl`: 0.22
10. `dbp` (이완기 혈압): 0.18
11. `hdl`: 0.12
12. `family_history_hypertension`: 0.12
13. `sbp` (수축기 혈압): 0.10
14. `waist_circumference`: 0.08
15. `pulse`: 0.06
16. `year`: 0.05
17. `fasting_time`: 0.05
18. `smoking_status`: 0.05
19. `smoking_fr_per_day`: 0.05
20. `gender`: 0.04

### 2.2. 고혈압 (hypertension_prevalence) 상관관계
1. `has_hypertension_diagnosis`: 0.85
2. `has_diabetes_diagnosis`: 0.42
3. `diabetes_prevalence`: 0.42
4. `hba1c`: 0.29
5. `fbs`: 0.25
6. `urine_glucose`: 0.19
7. `family_history_diabetes`: 0.16
8. `family_history_hypertension`: 0.15
9. `age`: 0.14
10. `sbp`: 0.14
11. `bmi`: 0.10
12. `height`: 0.10
13. `waist_circumference`: 0.08
14. `smoking_fr_per_day`: 0.06
15. `dbp`: 0.06
16. `smoking_status`: 0.05
17. `gender`: 0.05
18. `drinking_frequency`: 0.04
19. `total_cholesterol`: 0.04
20. `fasting_time`: 0.03

## 3. 시각화 및 통계 분석 결과 요약

`DataAnalyzer` 실행 결과에 따라 다음 리포트가 생성되었습니다.

- **타겟 분포**: `plots/target_distribution.png`에서 당뇨 및 고혈압의 클래스 불균형 확인.
- **결측치 분석**: `plots/missing_value_ratio.png`를 통해 데이터의 완전성 검토.
- **상관관계 행렬**: `plots/all_variables_correlation_matrix.png`에서 변수 간 전반적인 관계 시각화.
- **피처별 상세 분석**: 각 주요 피처와 타겟 간의 관계를 나타내는 박스플롯/카운트플롯 생성 (예: `hba1c_by_diabetes_prevalence.png`).

## 4. 데이터 특성 요약
- **직접 지표의 영향력**: 당뇨의 경우 `hba1c`, `fbs`가, 고혈압의 경우 `sbp`, `age` 등이 강력한 예측 인자임이 재확인되었습니다.
- **범주형 변수의 기여**: `urine_glucose`(요당) 수치가 질환 유병률과 유의미한 상관관계를 보입니다.
- **다중공선성**: 혈압 지표 간, 그리고 당 관련 지표 간 높은 상관관계가 존재하므로 모델링 시 피처 엔지니어링이 중요합니다.

## 5. 결과물 위치 (`docs/eda_results/knhanes/`)
- **Plots**: 시각화 이미지 40여 종 저장
- **CSV**: 요약 통계(`summary_statistics_all.csv`), 상관계수(`correlation_values.csv`), 결측치(`missing_values.csv`) 저장
