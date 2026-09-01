import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer

from src.components.model_trainer import ModelBundle

logger = logging.getLogger(__name__)


@dataclass
class FeatureMetadata:
    """
    원본 피처와 모델 입력 피처(One-Hot 인코딩 등 변환 후 피처) 간의 매핑 및 UI 표시명을 관리하는 메타데이터 클래스입니다.

    Attributes:
        model_feature_name: 전처리 후 모델 입력에 사용되는 피처명 (예: onehot__smoking_status_YES)
        original_feature_name: 원본 데이터셋의 피처명 (예: smoking_status)
        display_name: 사용자 UI/API 응답에 표시할 한글/직관적 명칭 (예: 흡연 여부)
    """

    model_feature_name: str
    original_feature_name: str
    display_name: str


@dataclass
class FeatureContribution:
    """
    단일 예측에서 특정 피처가 예측값에 미친 기여도를 나타내는 데이터 클래스입니다.

    Attributes:
        feature: 모델 피처명 또는 원본 피처명
        display_name: UI/API 표시명
        value: 해당 샘플의 실제 입력 피처 값
        shap_value: 해당 피처의 SHAP 기여도 수치
        direction: SHAP 값 부호에 따른 기여 방향 ("increase" 또는 "decrease")
    """

    feature: str
    display_name: str
    value: Any
    shap_value: float
    direction: Literal["increase", "decrease"]


@dataclass
class LocalExplanation:
    """
    단일 샘플(인스턴스)에 대한 로컬 SHAP 설명 결과를 담는 데이터 클래스입니다.

    Attributes:
        base_value: 모델의 기본 기대 예측값(Base value / Expected value)
        prediction_value: 모델의 최종 예측값(양성 클래스 확률 또는 모델 출력값)
        output_space: SHAP 값 및 예측값이 위치한 공간 ("probability", "log_odds", "raw")
        contributions: 개별 피처 기여도 리스트 (절대 기여도 기준 정렬)
    """

    base_value: float
    prediction_value: float
    output_space: Literal["probability", "log_odds", "raw"]
    contributions: list[FeatureContribution]

    @property
    def positive_contributions(self) -> list[FeatureContribution]:
        """위험 요인 (SHAP 기여도가 양수/증가 방향인 피처)"""
        return [c for c in self.contributions if c.shap_value > 0]

    @property
    def negative_contributions(self) -> list[FeatureContribution]:
        """보호 요인 (SHAP 기여도가 음수/감소 방향인 피처)"""
        return [c for c in self.contributions if c.shap_value < 0]


@dataclass
class ShapExplanationResult:
    """
    데이터셋 전체에 대한 글로벌 SHAP 분석 결과를 담는 데이터 클래스입니다.

    Attributes:
        feature_importances: 피처별 평균 절대 SHAP 값(|SHAP|) 및 상대 비중(importance_ratio) 데이터프레임
        shap_values: 각 샘플 및 피처에 대한 SHAP 기여도 행렬 (N, D)
        feature_names: 전처리 후 모델 입력 차원과 일치하는 피처 이름 리스트
        output_space: SHAP 값이 위치한 공간 ("probability", "log_odds", "raw")
    """

    feature_importances: pd.DataFrame
    shap_values: np.ndarray
    feature_names: list[str]
    output_space: Literal["probability", "log_odds", "raw"] = "probability"


class ShapExplainer:
    """
    SHAP(SHapley Additive exPlanations) 기반의 모델 설명 가능성(XAI) 분석 컴포넌트입니다.

    주요 기능:
    1. 전처리 파이프라인(`preprocessor`, `post_preprocessor`)과 모델을 유기적으로 연동하여 원본 입력 데이터도 자동 변환
    2. FeatureMetadata를 통한 원본 피처-모델 피처-표시명 매핑 관리
    3. 모델 알고리즘 유형(트리 기반, 선형 모델, 범용 predict_proba)에 따라 최적화된 SHAP Explainer 자동 선택
    4. 데이터셋 단위의 글로벌 설명(Global Explanation): 피처 중요도 및 상대 비중(importance_ratio), Beeswarm/Bar 플롯 시각화 저장
    5. 단일 샘플 단위의 로컬 설명(Local Explanation): Base value, Prediction value, Feature value, Direction을 포함한 구조화된 응답 제공
    """

    def __init__(
        self,
        model: Any,
        feature_names: list[str] | None = None,
        preprocessor: ColumnTransformer | None = None,
        post_preprocessor: ColumnTransformer | None = None,
        feature_metadata: list[FeatureMetadata] | None = None,
        background_data: np.ndarray | pd.DataFrame | None = None,
        background_size: int = 100,
        random_state: int = 42,
    ) -> None:
        """
        Args:
            model: 학습 완료된 머신러닝 분류기/회귀기 모델 객체
            feature_names: 최종 학습에 사용된 피처명 리스트 (선택 사항)
            preprocessor: 1차 전처리 파이프라인 (인코딩, 결측치 대치 등)
            post_preprocessor: 2차 전처리 파이프라인 (스케일러 등 리샘플링 이후 적용된 전처리기)
            feature_metadata: 원본 피처명 및 표시명을 포함하는 FeatureMetadata 리스트
            background_data: LinearExplainer 또는 Kernel/Permutation Explainer에서 참조할 배경 데이터셋
            background_size: 배경 데이터 최대 샘플링 크기 (기본값: 100)
            random_state: 재현성을 위한 난수 시드 (기본값: 42)
        """
        self.model = model
        self.feature_names = feature_names
        self.preprocessor = preprocessor
        self.post_preprocessor = post_preprocessor
        self.feature_metadata = feature_metadata or []
        self.background_size = background_size
        self.random_state = random_state

        # 배경 데이터가 전달된 경우 동일한 전처리 및 샘플링 과정을 거쳐 저장
        if background_data is not None:
            bg_prepared = self._prepare_data(background_data)
            if len(bg_prepared) > self.background_size:
                rng = np.random.RandomState(self.random_state)
                indices = rng.choice(len(bg_prepared), size=self.background_size, replace=False)
                self.background_data = bg_prepared[indices]
            else:
                self.background_data = bg_prepared
        else:
            self.background_data = None

        self._explainer: Any = None
        self._output_space: Literal["probability", "log_odds", "raw"] = "probability"

    @classmethod
    def from_bundle(
        cls,
        bundle: ModelBundle,
        background_data: np.ndarray | pd.DataFrame | None = None,
        background_size: int = 100,
        random_state: int = 42,
    ) -> "ShapExplainer":
        """
        학습 단계에서 생성된 `ModelBundle` 아티팩트로부터 `ShapExplainer` 인스턴스를 간편하게 생성합니다.
        """
        raw_metadata = getattr(bundle, "feature_metadata", None)
        metadata_objs: list[FeatureMetadata] | None = None
        if raw_metadata:
            metadata_objs = [
                item if isinstance(item, FeatureMetadata) else FeatureMetadata(**item) for item in raw_metadata
            ]

        return cls(
            model=bundle.model,
            feature_names=bundle.feature_names,
            preprocessor=bundle.preprocessor,
            post_preprocessor=bundle.post_preprocessor,
            feature_metadata=metadata_objs,
            background_data=background_data,
            background_size=background_size,
            random_state=random_state,
        )

    def _prepare_data(
        self,
        data: pd.DataFrame | np.ndarray | dict[str, Any] | pd.Series | list[Any],
    ) -> np.ndarray:
        """
        다양한 형태의 입력 데이터(dict, Series, DataFrame, ndarray)를 모델이 요구하는 전처리 파이프라인을 거쳐
        최종 2차원 넘파이 배열(Dense Matrix) 형태로 표준화 변환합니다.

        [처리 흐름]
        1. dict 또는 pd.Series 입력을 pd.DataFrame 형태로 구조화
        2. 1차 preprocessor(ColumnTransformer)가 존재하면 transform 수행 (fit은 절대 호출하지 않음)
        3. 2차 post_preprocessor(스케일러 등)가 존재하면 transform 수행
        4. 희소 행렬(Sparse) 또는 DataFrame을 순수 NumPy 2D 배열로 변환
        """
        if isinstance(data, dict):
            data = pd.DataFrame([data])
        elif isinstance(data, pd.Series):
            data = data.to_frame().T

        # 1차 전처리 적용 (원시 DataFrame -> 1차 변환 배열/데이터프레임)
        if self.preprocessor is not None and isinstance(data, pd.DataFrame):
            proc_data = self.preprocessor.transform(data)
        else:
            proc_data = data.to_numpy() if isinstance(data, pd.DataFrame) else np.asarray(data)

        # 2차 전처리 적용 (리샘플링 후 적용된 스케일러 등)
        if self.post_preprocessor is not None:
            proc_data = self.post_preprocessor.transform(proc_data)

        # 희소 행렬(Sparse Matrix) 처리 및 NumPy 배열 표준화
        if hasattr(proc_data, "toarray"):
            proc_data = proc_data.toarray()
        elif hasattr(proc_data, "to_numpy"):
            proc_data = proc_data.to_numpy()

        proc_data = np.asarray(proc_data)
        if proc_data.ndim == 1:
            proc_data = proc_data.reshape(1, -1)
        return proc_data

    def _get_feature_names(self, expected_len: int) -> list[str]:
        """
        전처리된 피처 차원 수(`expected_len`)와 일치하는 피처명 리스트를 도출합니다.
        """
        # 1. FeatureMetadata가 전달되어 있고 길이가 일치하는 경우
        if self.feature_metadata and len(self.feature_metadata) == expected_len:
            return [meta.model_feature_name for meta in self.feature_metadata]

        # 2. 기저장된 피처명이 유효한 경우
        if self.feature_names and len(self.feature_names) == expected_len:
            return list(self.feature_names)

        # 3. post_preprocessor로부터 추출 시도
        if self.post_preprocessor is not None and hasattr(self.post_preprocessor, "get_feature_names_out"):
            try:
                names = self.post_preprocessor.get_feature_names_out().tolist()
                if len(names) == expected_len:
                    return names
            except Exception:
                pass

        # 4. preprocessor로부터 추출 시도
        if self.preprocessor is not None and hasattr(self.preprocessor, "get_feature_names_out"):
            try:
                names = self.preprocessor.get_feature_names_out().tolist()
                if len(names) == expected_len:
                    return names
            except Exception:
                pass

        # 5. Fallback 기본 이름 생성
        return [f"feature_{i}" for i in range(expected_len)]

    def _init_explainer(self, sample_data: np.ndarray) -> Any:
        """
        모델의 알고리즘 유형에 가장 적합한 SHAP Explainer 객체를 지연 초기화(Lazy Initialization)합니다.

        [선택 전략]
        - 트리 기반 모델 (RandomForest, LightGBM, XGBoost, GradientBoosting, ExtraTrees):
          -> `shap.TreeExplainer` 사용 (output_space="probability" or "raw")
        - 선형 모델 (LogisticRegression, SGDClassifier):
          -> `shap.LinearExplainer` 사용 (output_space="log_odds" or "probability")
        - 그 외 모델 / Fallback:
          -> `predict_proba`가 지원되면 Positive Class(1) 확률 함수 `lambda x: self.model.predict_proba(x)[:, 1]`를 전달하여
             output_space="probability"인 `shap.Explainer` 생성
        """
        if self._explainer is not None:
            return self._explainer

        import shap

        model_name = self.model.__class__.__name__
        tree_models = {
            "RandomForestClassifier",
            "LGBMClassifier",
            "XGBClassifier",
            "GradientBoostingClassifier",
            "ExtraTreesClassifier",
        }
        linear_models = {"LogisticRegression", "SGDClassifier", "LinearSVC"}

        bg = self.background_data
        if bg is None:
            sample_size = min(self.background_size, len(sample_data))
            bg = sample_data[:sample_size]

        try:
            if model_name in tree_models:
                self._explainer = shap.TreeExplainer(self.model)
                self._output_space = "probability" if hasattr(self.model, "predict_proba") else "raw"
            elif model_name in linear_models:
                self._explainer = shap.LinearExplainer(self.model, bg)
                self._output_space = "log_odds" if model_name == "LogisticRegression" else "raw"
            else:
                if hasattr(self.model, "predict_proba"):
                    # Binary Classification의 Positive Class(1) 예측 확률 함수 전달
                    predict_fn = lambda x: self.model.predict_proba(x)[:, 1]
                    self._explainer = shap.Explainer(predict_fn, bg)
                    self._output_space = "probability"
                else:
                    self._explainer = shap.Explainer(self.model.predict, bg)
                    self._output_space = "raw"
        except Exception as e:
            logger.warning(
                f"Failed to initialize specific SHAP explainer for {model_name}, falling back to Generic Explainer: {e}"
            )
            if hasattr(self.model, "predict_proba"):
                predict_fn = lambda x: self.model.predict_proba(x)[:, 1]
                self._explainer = shap.Explainer(predict_fn, bg)
                self._output_space = "probability"
            else:
                self._explainer = shap.Explainer(self.model.predict, bg)
                self._output_space = "raw"

        return self._explainer

    @staticmethod
    def _extract_shap_matrix(shap_values_obj: Any, expected_shape: tuple[int, int]) -> np.ndarray:
        """
        SHAP 라이브러리가 반환하는 다양한 형태의 출력값(Explanation 객체, 3차원 배열, 이진 분류 리스트)에서
        양성 클래스(Class 1 / Positive Class) 기준의 2차원 (N_samples, N_features) SHAP 행렬을 일관되게 추출하고
        형태(Shape)를 엄격하게 검증합니다.

        [지원 형태]
        - shap.Explanation 객체 (.values)
        - list [class_0, class_1] -> class_1 선택
        - 3D ndarray (N, D, C) -> Positive class C=1 슬라이스 (:, :, 1) 선택
        - 2D ndarray (N, D)
        - 1D ndarray (D,) -> (1, D) reshape
        """
        n_samples, n_features = expected_shape

        if hasattr(shap_values_obj, "values"):
            values = shap_values_obj.values
        else:
            values = shap_values_obj

        # 1. 다중 클래스 / 이진 분류 리스트 형태 대응: [class_0, class_1]
        if isinstance(values, list):
            if len(values) == 2:
                values = values[1]  # Positive Class (1)
            elif len(values) == 1:
                values = values[0]
            else:
                values = values[1] if len(values) > 1 else values[0]

        values = np.asarray(values)

        # 2. 3차원 텐서 (샘플 수, 피처 수, 클래스 수) (N, D, C) 대응
        if values.ndim == 3:
            if values.shape[2] == 2:
                values = values[:, :, 1]  # Positive Class
            elif values.shape[2] == 1:
                values = values[:, :, 0]
            else:
                values = values[:, :, 1]  # 기본 Positive Class 슬라이스

        # 3. 1차원 단일 샘플 배열 (D,) 대응
        if values.ndim == 1:
            if len(values) == n_features:
                values = values.reshape(1, n_features)
            elif len(values) == n_samples * n_features:
                values = values.reshape(n_samples, n_features)

        # 4. 최종 shape validation
        if values.ndim != 2 or values.shape != expected_shape:
            raise ValueError(
                f"Extracted SHAP matrix shape {values.shape} does not match expected input shape {expected_shape}."
            )

        return values

    @staticmethod
    def _extract_base_value(shap_values_obj: Any, default_val: float = 0.0) -> float:
        """
        SHAP 객체로부터 Positive Class의 Base Value(Expected Value)를 추출합니다.
        """
        base_val = getattr(shap_values_obj, "base_values", None)
        if base_val is None:
            return default_val

        if isinstance(base_val, (list, np.ndarray)):
            base_arr = np.asarray(base_val)
            if base_arr.ndim == 0:
                return float(base_arr)
            if base_arr.ndim == 1:
                if len(base_arr) == 2:
                    return float(base_arr[1])  # Positive class base value
                return float(base_arr[0])
            if base_arr.ndim == 2:
                if base_arr.shape[1] == 2:
                    return float(base_arr[0, 1])
                return float(base_arr[0, 0])
        elif isinstance(base_val, (int, float)):
            return float(base_val)

        return default_val

    def explain_dataset(
        self,
        x: pd.DataFrame | np.ndarray,
        output_dir: Path | str | None = None,
        max_samples: int = 1000,
    ) -> ShapExplanationResult:
        """
        전체 검증/테스트 데이터셋에 대해 SHAP 값을 계산하고, 글로벌 피처 중요도 테이블 및 시각화 플롯을 생성합니다.
        """
        out_dir = Path(output_dir) if output_dir is not None else None

        # 1. Dataset Sampling
        if isinstance(x, (pd.DataFrame, pd.Series)):
            if len(x) > max_samples:
                x = x.sample(n=max_samples, random_state=self.random_state)
        elif isinstance(x, np.ndarray):
            if len(x) > max_samples:
                rng = np.random.RandomState(self.random_state)
                idx = rng.choice(len(x), size=max_samples, replace=False)
                x = x[idx]

        # 2. 데이터 전처리
        x_proc = self._prepare_data(x)

        # 3. Explainer 초기화 및 SHAP 값 산출
        explainer = self._init_explainer(x_proc)
        shap_values_obj = explainer(x_proc)

        # 4. 피처명 및 SHAP 행렬 추출 및 검증
        feature_names = self._get_feature_names(x_proc.shape[1])
        shap_matrix = self._extract_shap_matrix(shap_values_obj, x_proc.shape)

        # 5. 글로벌 피처 중요도 (|SHAP| 평균) 및 상대적 비중 (importance_ratio) 계산
        mean_abs_shap = np.mean(np.abs(shap_matrix), axis=0)
        total_importance = float(np.sum(mean_abs_shap))
        importance_ratio = mean_abs_shap / total_importance if total_importance > 0 else np.zeros_like(mean_abs_shap)

        df_importance = (
            pd.DataFrame(
                {
                    "feature": feature_names,
                    "importance": mean_abs_shap,
                    "importance_ratio": importance_ratio,
                }
            )
            .sort_values(by="importance", ascending=False)
            .reset_index(drop=True)
        )

        # 6. 아티팩트 디스크 저장 (요청된 경우)
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            df_importance.to_csv(out_dir / "shap_feature_importance.csv", index=False)
            self._save_plots(shap_matrix, x_proc, feature_names, out_dir)

        return ShapExplanationResult(
            feature_importances=df_importance,
            shap_values=shap_matrix,
            feature_names=feature_names,
            output_space=self._output_space,
        )

    def explain_instance(
        self,
        x_single: pd.DataFrame | pd.Series | np.ndarray | dict[str, Any],
        top_k: int | None = None,
    ) -> LocalExplanation:
        """
        단일 예측 대상(환자/사용자 1명)에 대해 각 피처가 예측값에 미친 기여도를 계산하여 구조화된 `LocalExplanation` 객체를 반환합니다.

        [실행 흐름]
        1. 원본 입력 피처 값(`raw_values`)을 사전 캡처
        2. 단일 샘플 입력을 전처리 후 2차원 (1, D) 형태로 변환
        3. 모델의 실제 예측값(Positive Class 확률 또는 모델 출력값) 산출
        4. SHAP 값 계산 및 추출, base_value 도출
        5. FeatureMetadata 및 원본/인코딩 값을 결합하여 `FeatureContribution` 객체 리스트 구성
        6. 기여도의 절대값(|SHAP|)을 기준으로 내림차순 정렬 및 top_k 필터링
        7. `LocalExplanation` 반환
        """
        # 1. 원본 입력 피처 값 캡처
        raw_feature_map: dict[str, Any] = {}
        if isinstance(x_single, dict):
            raw_feature_map = x_single
        elif isinstance(x_single, pd.Series):
            raw_feature_map = x_single.to_dict()
        elif isinstance(x_single, pd.DataFrame):
            raw_feature_map = x_single.iloc[0].to_dict()

        # 2. 전처리 및 2D 배열 정렬
        x_proc = self._prepare_data(x_single)

        # 3. 모델 예측값 계산
        if hasattr(self.model, "predict_proba"):
            prediction_value = float(self.model.predict_proba(x_proc)[0, 1])
        elif hasattr(self.model, "predict"):
            pred = self.model.predict(x_proc)[0]
            prediction_value = float(pred)
        else:
            prediction_value = 0.0

        # 4. SHAP 값 계산 및 추출
        explainer = self._init_explainer(x_proc)
        shap_values_obj = explainer(x_proc)
        feature_names = self._get_feature_names(x_proc.shape[1])
        shap_matrix = self._extract_shap_matrix(shap_values_obj, x_proc.shape)

        base_value = self._extract_base_value(shap_values_obj, default_val=0.0)

        # 5. 메타데이터 매핑 딕셔너리 생성
        meta_by_model_feat: dict[str, FeatureMetadata] = {m.model_feature_name: m for m in self.feature_metadata}

        instance_shap = shap_matrix[0]
        proc_values = x_proc[0]

        contributions: list[FeatureContribution] = []
        for i, feat_name in enumerate(feature_names):
            shap_val = float(instance_shap[i])
            direction: Literal["increase", "decrease"] = "increase" if shap_val >= 0 else "decrease"

            meta = meta_by_model_feat.get(feat_name)
            if meta is not None:
                display_name = meta.display_name
                # 원본 피처 값이 있으면 우선 사용, 없으면 전처리된 값 사용
                actual_val = raw_feature_map.get(meta.original_feature_name, proc_values[i])
                feature_key = meta.model_feature_name
            else:
                display_name = feat_name
                actual_val = raw_feature_map.get(feat_name, proc_values[i])
                feature_key = feat_name

            contributions.append(
                FeatureContribution(
                    feature=feature_key,
                    display_name=display_name,
                    value=actual_val,
                    shap_value=shap_val,
                    direction=direction,
                )
            )

        # 6. 절대값 기준 내림차순 정렬
        contributions.sort(key=lambda item: abs(item.shap_value), reverse=True)

        if top_k is not None:
            contributions = contributions[:top_k]

        return LocalExplanation(
            base_value=base_value,
            prediction_value=prediction_value,
            output_space=self._output_space,
            contributions=contributions,
        )

    def _save_plots(
        self,
        shap_matrix: np.ndarray,
        x_proc: np.ndarray,
        feature_names: list[str],
        output_dir: Path,
    ) -> None:
        """
        SHAP 분석 결과 플롯(Beeswarm 요약 플롯, Bar 중요도 플롯)을 파일로 렌더링하여 저장합니다.
        """
        import shap

        # 1. Beeswarm 요약 플롯
        try:
            fig = plt.figure(figsize=(10, 6))
            shap.summary_plot(
                shap_matrix,
                x_proc,
                feature_names=feature_names,
                show=False,
            )
            plt.tight_layout()
            fig.savefig(output_dir / "shap_summary.png", bbox_inches="tight")
            plt.close(fig)
        except Exception as e:
            logger.warning(f"Failed to generate SHAP summary plot: {e}")
            plt.close("all")

        # 2. Bar 플롯
        try:
            fig = plt.figure(figsize=(10, 6))
            shap.summary_plot(
                shap_matrix,
                x_proc,
                feature_names=feature_names,
                plot_type="bar",
                show=False,
            )
            plt.tight_layout()
            fig.savefig(output_dir / "shap_bar.png", bbox_inches="tight")
            plt.close(fig)
        except Exception as e:
            logger.warning(f"Failed to generate SHAP bar plot: {e}")
            plt.close("all")
