from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.components.data_analyzer import DataAnalyzer
from src.components.data_loader import DataLoader
from src.components.data_preprocessor import KnhanesPreprocessor
from src.components.data_splitter import DataSplitter
from src.components.model_evaluator import ModelEvaluator
from src.components.model_trainer import BinaryClassificationModelTrainer
from src.components.shap_explainer import ShapExplainer
from src.components.threshold_optimizer import ThresholdOptimizer
from src.enums import ModelAlgorithm, ModelType
from src.knhanes_label_configs import DISEASE_LABEL_VAR
from src.knhanes_preprocessing_configs import TRAINING_META_VARS


@pytest.fixture
def raw_knhanes_dataset(tmp_path: Path) -> Path:
    """100행 규모의 KNHANES 형식 원시 데이터 CSV 파일 생성"""
    np.random.seed(42)
    n_samples = 120

    raw_data = {
        "sex": np.random.choice([1, 2], size=n_samples),
        "age": np.random.randint(20, 80, size=n_samples),
        "HE_ht": np.random.normal(168, 8, size=n_samples),
        "HE_wt": np.random.normal(65, 12, size=n_samples),
        "HE_wc": np.random.normal(82, 10, size=n_samples),
        "HE_BMI": np.random.normal(23.5, 3.5, size=n_samples),
        "BD1": np.random.choice([1, 2, 8], size=n_samples),
        "BD1_11": np.random.choice([1, 2, 3, 4, 5, 8], size=n_samples),
        "BD2_1": np.random.choice([1, 2, 3, 4, 8], size=n_samples),
        "BS3_1": np.random.choice([1, 2, 3, 8], size=n_samples),
        "BS3_2": np.random.choice([10, 20, 888, 999], size=n_samples),
        "HE_chol": np.random.normal(195, 30, size=n_samples),
        "HE_HDL_st2": np.random.normal(52, 12, size=n_samples),
        "HE_TG": np.random.normal(140, 50, size=n_samples),
        "HE_ast": np.random.normal(25, 8, size=n_samples),
        "HE_alt": np.random.normal(24, 10, size=n_samples),
        "HE_crea": np.random.normal(0.9, 0.2, size=n_samples),
        "HE_Upro": np.random.choice([0, 1, 2], size=n_samples),
        "DE1_pr": np.random.choice([0, 1], size=n_samples, p=[0.75, 0.25]),
        "HE_sbp": np.random.normal(122, 15, size=n_samples),
        "HE_dbp": np.random.normal(78, 10, size=n_samples),
        "DI1_pr": np.random.choice([0, 1], size=n_samples, p=[0.7, 0.3]),
        "HE_DMfh1": np.random.choice([0, 1, 9], size=n_samples),
        "HE_DMfh2": np.random.choice([0, 1, 9], size=n_samples),
        "HE_DMfh3": np.random.choice([0, 1, 8, 9], size=n_samples),
    }

    df = pd.DataFrame(raw_data)
    csv_path = tmp_path / "raw_knhanes_sample.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


def test_full_ml_pipeline_e2e(raw_knhanes_dataset: Path, tmp_path: Path):
    """
    KNHANES 원시 데이터 로딩부터 최종 SHAP 설명 도출까지
    전체 머신러닝 파이프라인의 End-to-End 동작을 검증합니다.
    """
    pipeline_dir = tmp_path / "pipeline_run"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    # 1. DataLoader: 원시 파일 로드
    loader = DataLoader()
    raw_df = loader.load(raw_knhanes_dataset)
    assert len(raw_df) == 120

    # 2. DataAnalyzer: EDA 실행 및 통계/플롯 산출
    eda_dir = pipeline_dir / "eda"
    analyzer = DataAnalyzer(df=raw_df, output_dir_path=eda_dir)
    analyzer.run_full_eda(target="DE1_pr")
    assert (eda_dir / "csv" / "dataset_summary.csv").exists()
    assert (eda_dir / "plots" / "all_variables_correlation_matrix.png").exists()

    # 3. KnhanesPreprocessor: 라벨이 생성된 데이터의 도메인 전처리
    labeled_df = raw_df.assign(
        ID=[f"A{index}" for index in range(len(raw_df))],
        ID_fam=[f"F{index}" for index in range(len(raw_df))],
        year=2022,
        wt_itvex=1.0,
        wt_tot=1.0,
        kstrata=1,
        psu=1,
        disease_label=raw_df["DE1_pr"],
    )
    preprocessed_dir = pipeline_dir / "preprocessed"
    preprocessor = KnhanesPreprocessor(
        use_case=ModelType.DIABETES_RISK,
        output_dir=preprocessed_dir,
    )
    clean_df = preprocessor.preprocess_labeled(labeled_df)
    preprocessor.save(clean_df)
    assert (preprocessed_dir / f"{ModelType.DIABETES_RISK}.parquet").exists()
    assert DISEASE_LABEL_VAR in clean_df.columns
    assert "당뇨병 가족력 보유 여부" in clean_df.columns

    # 4. DataSplitter: Stratified 분할 (Train/Val/Test)
    split_dir = pipeline_dir / "split"
    splitter = DataSplitter(
        output_dir=split_dir,
        train_size=0.6,
        val_size=0.2,
        test_size=0.2,
        random_state=42,
    )
    split_data = splitter.split(clean_df.drop(columns=TRAINING_META_VARS), target_var=DISEASE_LABEL_VAR)
    splitter.save_to_parquet(split_data)
    assert (split_dir / "X_train.parquet").exists()
    assert (split_dir / "y_test.parquet").exists()

    # 5. BinaryClassificationModelTrainer: 모델 학습 및 번들 패키징
    model_dir = pipeline_dir / "models"
    trainer = BinaryClassificationModelTrainer(
        x_train=split_data.X_train,
        y_train=split_data.y_train,
        algorithm=ModelAlgorithm.RANDOM_FOREST,
        use_resampling=True,
        model_dir=model_dir,
        output_filename="diabetes_model",
        random_state=42,
    )
    bundle = trainer.train(auto_save=True)
    saved_model_path = model_dir / f"diabetes_model_{ModelAlgorithm.RANDOM_FOREST}_resampled.pkl"
    assert saved_model_path.exists()
    assert bundle.feature_metadata is not None

    # ModelBundle.transform 검증
    val_proc = bundle.transform(split_data.X_validation)
    assert isinstance(val_proc, np.ndarray)

    # 6. ThresholdOptimizer: 검증 세트 기반 최적 임계값 탐색
    val_probs = bundle.model.predict_proba(val_proc)[:, 1]
    optimizer = ThresholdOptimizer(
        min_recall=0.7,
        strategy="f1",
        strict=False,
    )
    best_threshold_res = optimizer.optimize(
        y_true=split_data.y_validation,
        y_prob=val_probs,
    )
    assert 0.0 < best_threshold_res.threshold < 1.0

    # 번들에 최적 임계값 반영
    bundle.threshold = best_threshold_res.threshold

    # 7. ModelEvaluator: 테스트 세트 평가 및 리포트 저장
    eval_dir = pipeline_dir / "evaluation"
    evaluator = ModelEvaluator.from_bundle(
        bundle=bundle,
        x_test=split_data.X_test,
        y_test=split_data.y_test,
        output_dir=eval_dir,
    )
    eval_result = evaluator.evaluate()
    evaluator.save(eval_result)
    assert (eval_dir / "metrics.csv").exists()
    assert (eval_dir / "confusion_matrix.png").exists()
    assert (eval_dir / "roc_curve.png").exists()
    assert (eval_dir / "precision_recall_curve.png").exists()
    assert eval_result.metrics.f1 >= 0.0

    # 8. ShapExplainer: XAI 글로벌 및 로컬 설명 도출
    shap_dir = pipeline_dir / "shap"
    explainer = ShapExplainer.from_bundle(
        bundle=bundle,
        background_data=split_data.X_train,
        background_size=30,
        random_state=42,
    )

    # 8-1. 글로벌 분석
    global_shap = explainer.explain_dataset(
        x=split_data.X_test,
        output_dir=shap_dir,
        max_samples=20,
    )
    assert (shap_dir / "shap_feature_importance.csv").exists()
    assert (shap_dir / "shap_summary.png").exists()
    assert (shap_dir / "shap_bar.png").exists()
    assert len(global_shap.feature_importances) == len(bundle.feature_names)

    # 8-2. 로컬 분석 (단일 샘플 설명 및 프로퍼티 접근)
    single_instance = split_data.X_test.iloc[0]
    local_exp = explainer.explain_instance(single_instance, top_k=5)
    assert len(local_exp.contributions) <= 5
    assert isinstance(local_exp.positive_contributions, list)
    assert isinstance(local_exp.negative_contributions, list)
