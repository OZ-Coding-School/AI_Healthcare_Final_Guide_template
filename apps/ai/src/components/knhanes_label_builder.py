import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype

from core.logger import configure_logger
from src.components.knhanes_multi_year_loader import (
    AGE_VAR,
    OFFICIAL_HYPERTENSION_VAR,
    YEAR_VAR,
    KnhanesDataValidationError,
)
from src.enums import ModelType
from src.knhanes_label_configs import (
    DIABETES_FASTING_GLUCOSE_MIN,
    DIABETES_HBA1C_MIN,
    DISEASE_LABEL_VAR,
    FASTING_MIN_HOURS,
    HYPERTENSION_DIASTOLIC_MIN,
    HYPERTENSION_MEDICATION_CODES,
    HYPERTENSION_SYSTOLIC_MIN,
    MODEL_REQUIRED_RESPONSE_VARS_MAP,
    OFFICIAL_DIABETES_CODE,
    UNKNOWN_RESPONSE_CODE,
)
from src.knhanes_merge_configs import HE_HP_HYPERTENSION_CODE_BY_YEAR, KNHANES_ADULT_MIN_AGE
from src.knhanes_preprocessing_configs import (
    MODEL_LABEL_SOURCE_VARS_MAP,
    MODEL_OFFICIAL_LABEL_VAR_MAP,
    PREGNANCY_EXCLUSION_VARS,
)

logger = configure_logger("KNHANES Label Builder")

FASTING_GLUCOSE_VAR = "HE_glu"
FASTING_HOURS_VAR = "HE_fst"


@dataclass(frozen=True)
class KnhanesLabelReport:
    model_type: ModelType
    yearly_summary: pd.DataFrame
    official_comparison: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_type": str(self.model_type),
            "yearly_summary": self.yearly_summary.to_dict(orient="records"),
            "official_comparison": self.official_comparison,
        }

    def save(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


class KnhanesLabelBuilder:
    def __init__(self, strict_official_match: bool = True) -> None:
        self.strict_official_match = strict_official_match

    def build(self, df: pd.DataFrame, model_type: ModelType) -> tuple[pd.DataFrame, KnhanesLabelReport]:
        """
        병합된 원시 데이터로 질환별 학습 대상과 B안 라벨을 만듭니다.

        1. 입력 컬럼과 조사연도 검증
        2. 19세 이상 필터, 임신 중 응답자 제외
        3. 공복 8시간 미만의 공복혈당을 결측 처리
        4. 양성·음성 판정, 판정할 수 없는 행 제외
        5. 공식 분류와 대조하고 리포트 생성
        """
        self._validate_input(df, model_type)

        adults = df[df[AGE_VAR].ge(KNHANES_ADULT_MIN_AGE)]
        pregnant = self._pregnant_mask(adults)
        cohort = adults[~pregnant].copy()

        non_fasting = self._non_fasting_glucose_mask(cohort)
        cohort[FASTING_GLUCOSE_VAR] = cohort[FASTING_GLUCOSE_VAR].mask(non_fasting)

        positive = self._positive_mask(cohort, model_type)
        negative = ~positive & self._can_confirm_negative(cohort, model_type)

        labeled = cohort[positive | negative].copy()
        if labeled.empty:
            raise KnhanesDataValidationError(f"{model_type}: no rows can be labeled")
        labeled[DISEASE_LABEL_VAR] = positive[labeled.index].astype(int)

        report = KnhanesLabelReport(
            model_type=model_type,
            yearly_summary=self._build_yearly_summary(adults, pregnant, non_fasting, labeled),
            official_comparison=self._compare_with_official(labeled, model_type),
        )
        self._handle_official_mismatch(model_type, report.official_comparison)

        return labeled.reset_index(drop=True), report

    @staticmethod
    def _validate_input(df: pd.DataFrame, model_type: ModelType) -> None:
        source_vars = [
            *MODEL_LABEL_SOURCE_VARS_MAP[model_type],
            *MODEL_REQUIRED_RESPONSE_VARS_MAP[model_type],
            *PREGNANCY_EXCLUSION_VARS,
            MODEL_OFFICIAL_LABEL_VAR_MAP[model_type],
            AGE_VAR,
            FASTING_GLUCOSE_VAR,
            FASTING_HOURS_VAR,
        ]
        required_vars = list(dict.fromkeys([YEAR_VAR, *source_vars]))

        missing_vars = [var_name for var_name in required_vars if var_name not in df.columns]
        if missing_vars:
            raise KnhanesDataValidationError(f"{model_type}: missing label columns: {missing_vars}")

        non_numeric_vars = [var_name for var_name in required_vars if not is_numeric_dtype(df[var_name])]
        if non_numeric_vars:
            raise KnhanesDataValidationError(f"{model_type}: label columns must be numeric: {non_numeric_vars}")

        unsupported_years = sorted(set(df[YEAR_VAR].dropna()) - set(HE_HP_HYPERTENSION_CODE_BY_YEAR))
        if df[YEAR_VAR].isna().any() or unsupported_years:
            raise KnhanesDataValidationError(f"{model_type}: invalid survey years: {unsupported_years or 'missing'}")

    @staticmethod
    def _pregnant_mask(df: pd.DataFrame) -> pd.Series:
        return df["HE_prg"].eq(1) | df["HE_dprg"].notna()

    @staticmethod
    def _non_fasting_glucose_mask(df: pd.DataFrame) -> pd.Series:
        return df[FASTING_GLUCOSE_VAR].notna() & ~df[FASTING_HOURS_VAR].ge(FASTING_MIN_HOURS)

    @classmethod
    def _positive_mask(cls, df: pd.DataFrame, model_type: ModelType) -> pd.Series:
        if model_type == ModelType.DIABETES_RISK:
            return (
                df["DE1_dg"].eq(1)
                | df["DE1_31"].eq(1)
                | df["DE1_32"].eq(1)
                | df[FASTING_GLUCOSE_VAR].ge(DIABETES_FASTING_GLUCOSE_MIN)
                | df["HE_HbA1c"].ge(DIABETES_HBA1C_MIN)
            )
        return df["DI1_pr"].eq(1) | cls._hypertension_official_criteria_mask(df)

    @staticmethod
    def _hypertension_official_criteria_mask(df: pd.DataFrame) -> pd.Series:
        return (
            df["HE_sbp"].ge(HYPERTENSION_SYSTOLIC_MIN)
            | df["HE_dbp"].ge(HYPERTENSION_DIASTOLIC_MIN)
            | df["DI1_2"].isin(HYPERTENSION_MEDICATION_CODES)
        )

    @staticmethod
    def _can_confirm_negative(df: pd.DataFrame, model_type: ModelType) -> pd.Series:
        """
        양성이 아닌 행을 음성으로 확정하려면 검사값과 진단·치료 응답이 모두 있어야 합니다.
        """
        if model_type == ModelType.DIABETES_RISK:
            measured = df[FASTING_GLUCOSE_VAR].notna() & df["HE_HbA1c"].notna()
        else:
            measured = df["HE_sbp"].notna() & df["HE_dbp"].notna()

        responses = df[MODEL_REQUIRED_RESPONSE_VARS_MAP[model_type]]
        answered = responses.notna().all(axis=1) & responses.ne(UNKNOWN_RESPONSE_CODE).all(axis=1)
        return measured & answered

    @staticmethod
    def _build_yearly_summary(
        adults: pd.DataFrame,
        pregnant: pd.Series,
        non_fasting: pd.Series,
        labeled: pd.DataFrame,
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for year in sorted(adults[YEAR_VAR].unique()):
            year_adults = adults[YEAR_VAR].eq(year)
            year_labels = labeled.loc[labeled[YEAR_VAR].eq(year), DISEASE_LABEL_VAR]
            pregnant_count = int(pregnant[year_adults].sum())
            positive_count = int(year_labels.sum())
            rows.append(
                {
                    "year": int(year),
                    "adults": int(year_adults.sum()),
                    "pregnant_excluded": pregnant_count,
                    "non_fasting_glucose_masked": int(
                        non_fasting.reindex(adults.index[year_adults], fill_value=False).sum()
                    ),
                    "unlabeled_excluded": int(year_adults.sum()) - pregnant_count - len(year_labels),
                    "labeled": len(year_labels),
                    "positive": positive_count,
                    "negative": len(year_labels) - positive_count,
                    "positive_rate": round(positive_count / len(year_labels), 4) if len(year_labels) else None,
                }
            )
        return pd.DataFrame(rows)

    @classmethod
    def _compare_with_official(cls, labeled: pd.DataFrame, model_type: ModelType) -> dict[str, Any]:
        official_var = MODEL_OFFICIAL_LABEL_VAR_MAP[model_type]
        compared = labeled[labeled[official_var].notna()]

        if model_type == ModelType.DIABETES_RISK:
            official_positive = compared[official_var].eq(OFFICIAL_DIABETES_CODE)
            current_prevalence_only = pd.Series(False, index=compared.index)
        else:
            hypertension_codes = compared[YEAR_VAR].map(HE_HP_HYPERTENSION_CODE_BY_YEAR)
            official_positive = compared[OFFICIAL_HYPERTENSION_VAR].eq(hypertension_codes)
            # 공식 분류에 없는 현재 유병(DI1_pr = 1) 기준만으로 양성이 된 행
            current_prevalence_only = compared["DI1_pr"].eq(1) & ~cls._hypertension_official_criteria_mask(compared)

        label_positive = compared[DISEASE_LABEL_VAR].eq(1)
        label_only_positive = label_positive & ~official_positive
        official_only_positive = official_positive & ~label_positive
        designed_difference = label_only_positive & current_prevalence_only
        mismatch_count = int((label_only_positive | official_only_positive).sum())

        return {
            "official_var": official_var,
            "compared_rows": len(compared),
            "both_positive": int((label_positive & official_positive).sum()),
            "both_negative": int((~label_positive & ~official_positive).sum()),
            "label_only_positive": int(label_only_positive.sum()),
            "official_only_positive": int(official_only_positive.sum()),
            "agreement_rate": round(1 - mismatch_count / len(compared), 4) if len(compared) else None,
            "designed_difference": int(designed_difference.sum()),
            "unexplained_mismatch": mismatch_count - int(designed_difference.sum()),
            "labeled_without_official": len(labeled) - len(compared),
        }

    def _handle_official_mismatch(self, model_type: ModelType, comparison: dict[str, Any]) -> None:
        if comparison["unexplained_mismatch"] == 0:
            return

        message = f"{model_type}: label does not match official classification: {comparison}"
        if self.strict_official_match:
            raise KnhanesDataValidationError(message)
        logger.warning(message)
