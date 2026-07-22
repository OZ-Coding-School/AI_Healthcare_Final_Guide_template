import json
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from core import settings
from core.enums import DrinkingFrequency, DrinkingStatus, SmokingStatus, UrinalysisStatus


class KnhanesPreprocessor:
    def __init__(self, usable_vars_path: str | Path):
        self.usable_vars_path = usable_vars_path
        self.usable_vars_map = self._load_usable_vars_map()
        self.target_fields = self._get_target_fields()
        self.processed_data_dir: Path = settings.DATA_DIR / "processed/knhanes"

    def _load_usable_vars_map(self) -> list[dict[str, Any]]:
        with open(self.usable_vars_path, encoding="utf-8") as f:
            return json.load(f)

    def _get_target_fields(self) -> list[str]:
        """KNHANES 변수명과 매핑된 필드명 딕셔너리 반환"""
        return [category["name"] for category in self.usable_vars_map]

    def save_parquet(
        self,
        df: pd.DataFrame,
        output_file_name: str,
        compression: Literal["snappy", "gzip", "brotli", "lz4", "zstd"] = "snappy",
    ) -> None:
        """
        전처리된 데이터를 Parquet으로 저장한다.
        Args:
            output_path: 저장할 parquet 파일 경로
            compression: 압축 방식 (snappy, gzip, brotli, zstd)
        """
        if df is None:
            raise ValueError("No processed dataframe. Call preprocess() first.")

        output_path = self.processed_data_dir / output_file_name
        if not self.processed_data_dir.exists():
            self.processed_data_dir.mkdir(parents=True, exist_ok=True)

        df.to_parquet(
            output_path,
            index=False,
            compression=compression,
        )

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """KNHANES raw 데이터를 전처리하여 학습/예측에 적합한 형태로 변환"""
        # 1. 필요한 변수만 추출
        processed_df = df.reindex(columns=self.target_fields).copy().astype(object)

        # 2. 컬럼명 변경 (KNHANES 변수명 -> 앱 내 식별 필드명)
        field_name_map = {
            var["name"]: var["mapped_model_field"] for var in self.usable_vars_map if "mapped_model_field" in var
        }
        processed_df = processed_df.rename(columns=field_name_map)

        # 3. 당뇨 또는 고혈압 조사 대상이 아닌 행 모두 제거
        processed_df = self._delete_not_applicable_rows(processed_df)

        # 3. 데이터 타입 변환 및 결측치 처리
        processed_df = self._clean_data(processed_df)

        # 4. 파생 변수 생성 (필요한 경우)
        processed_df = self._add_derived_features(processed_df)

        # 5. 불필요한 변수 제거
        processed_df = self._drop_unusable_vars(processed_df)

        return processed_df

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터 정제 (결측치 처리, 인코딩 등)"""
        df = self._clean_smoking_vars(df)
        df = self._clean_drinking_vars(df)
        df = self._clean_diagnosis_prevalence_vars(df)
        df = self._clean_urine_status_vars(df)
        df = self._encode_gender(df)
        df = self._drop_unperformed_blood_test_rows(df)
        return df

    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        파생 변수 계산
        1. bmi
        2. 당뇨 가족력
        3. 고혈압 가족력
        """
        df = self._add_derived_bmi(df)
        df = self._add_derived_family_history_diabetes(df)
        df = self._add_derived_family_history_hypertension(df)

        return df

    @staticmethod
    def _drop_unusable_vars(df: pd.DataFrame) -> pd.DataFrame:
        drop_cols = [
            "drinking_amount_per_session2",
            "family_history_hypertension1",
            "family_history_hypertension2",
            "family_history_hypertension3",
            "family_history_diabetes1",
            "family_history_diabetes2",
            "family_history_diabetes3",
        ]
        return df.drop(columns=drop_cols)

    @staticmethod
    def _delete_not_applicable_rows(df: pd.DataFrame) -> pd.DataFrame:
        """
        당뇨 또는 고혈압 조사 대상이 아닌 행을 모두 제거하고 데이터프레임을 반환하는 함수
        """
        # 19세 미만의 경우 만성질환(당뇨, 고혈압 조사 대상이 아님)
        adult_mask = df["age"] >= 19
        # 당뇨나 고혈압 유병 여부가 0 또는 1인 것만 남겨둠
        valid_mask = df["hypertension_prevalence"].isin([0, 1]) | df["diabetes_prevalence"].isin([0, 1])
        return df[adult_mask & valid_mask].copy()

    @staticmethod
    def _add_derived_bmi(df: pd.DataFrame) -> pd.DataFrame:
        if "bmi" not in df.columns or df["bmi"].isnull().any():
            if "height" in df.columns and "weight" in df.columns:
                # height(cm) -> m
                h_m = df["height"] / 100
                calculated_bmi = df["weight"] / (h_m**2)
                if "bmi" in df.columns:
                    df["bmi"] = df["bmi"].fillna(calculated_bmi)
                else:
                    df["bmi"] = calculated_bmi

        return df

    @staticmethod
    def _add_derived_family_history_diabetes(df: pd.DataFrame) -> pd.DataFrame:
        if "family_history_diabetes" not in df.columns:
            df["family_history_diabetes"] = (
                (df["family_history_diabetes1"] == 1)
                | (df["family_history_diabetes2"] == 1)
                | (df["family_history_diabetes3"] == 1)
            ).astype(int)

        return df

    @staticmethod
    def _add_derived_family_history_hypertension(df: pd.DataFrame) -> pd.DataFrame:
        if "family_history_hypertension" not in df.columns:
            df["family_history_hypertension"] = (
                (df["family_history_hypertension1"] == 1)
                | (df["family_history_hypertension2"] == 1)
                | (df["family_history_hypertension3"] == 1)
            ).astype(int)

        return df

    @staticmethod
    def _encode_gender(df: pd.DataFrame) -> pd.DataFrame:
        """
        성별 인코딩 처리 함수
        1(남) -> M,
        2(여) -> F
        """
        df["gender"] = df["gender"].map({1: "M", 2: "F"})
        return df

    @staticmethod
    def _clean_smoking_vars(df: pd.DataFrame) -> pd.DataFrame:
        """
        흡연 관련 변수 인코딩 및 결측치 처리 함수
        """
        if "smoking_status" in df.columns:
            # 흡연 상태 (1,2: CURRENT, 3: FORMER, 그외: NEVER) - HabitStatus Enum 대응
            # BS3_1:
            # 1.매일피움, 2.가끔피움 -> CURRENT
            # 3.과거엔 피웠으나 현재 안피움 -> FORMER
            # 8.비해당 -> NEVER
            # 9.모름, 무응답 -> 결측치 처리
            df["smoking_status"] = df["smoking_status"].map(
                {
                    1: SmokingStatus.CURRENT,
                    2: SmokingStatus.CURRENT,
                    3: SmokingStatus.FORMER,
                    8: SmokingStatus.NEVER,
                    9: np.nan,
                }
            )

        if "smoking_fr_per_day" in df.columns:
            # 888.비해당(소아), 999.모름, 무응답 -> 결측치 처리
            mask = df["smoking_fr_per_day"].isin([888, 999])
            df.loc[mask, "smoking_fr_per_day"] = np.nan

            # 흡연 상태가 결측이면 일일흡연량도 결측치처리
            is_status_nan = df["smoking_status"] == np.nan
            df.loc[is_status_nan, "smoking_fr_per_day"] = np.nan

            # 흡연 상태가 FORMER, NEVER이면 일일흡연량은 0으로 처리
            mask = df["smoking_status"].isin([SmokingStatus.FORMER, SmokingStatus.NEVER])
            df.loc[mask, "smoking_fr_per_day"] = 0

        return df

    @staticmethod
    def _clean_drinking_vars(df: pd.DataFrame) -> pd.DataFrame:
        """
        음주 관련 변수 인코딩 및 결측치 처리 함수
        """
        if "drinking_experience" in df.columns:
            # 음주 경험이 없을 때 변수 처리
            never_mask = df["drinking_experience"] == 1
            df.loc[never_mask, "drinking_experience"] = DrinkingStatus.NEVER
            df.loc[never_mask, "drinking_frequency"] = DrinkingFrequency.NOT_APPLICABLE
            df.loc[never_mask, "drinking_amount_per_session"] = 0

            # 이전 음주 경험만 있을 때 변수 처리
            former_mask = (df["drinking_experience"] == 2) & (df["drinking_frequency"] == 1)
            df.loc[former_mask, "drinking_experience"] = DrinkingStatus.FORMER
            df.loc[former_mask, "drinking_frequency"] = DrinkingFrequency.NOT_APPLICABLE
            df.loc[former_mask, "drinking_amount_per_session"] = 0

            # 현재 음주를 하고 있는 경우 변수 처리
            current_mask = (df["drinking_experience"] == 2) & (df["drinking_frequency"].isin([2, 3, 4, 5, 6]))
            df.loc[current_mask, "drinking_experience"] = DrinkingStatus.CURRENT
            df.loc[current_mask, "drinking_frequency"] = df["drinking_frequency"].map(
                {
                    2: DrinkingFrequency.LESS_THAN_MONTHLY,
                    3: DrinkingFrequency.MONTHLY,
                    4: DrinkingFrequency.MONTHLY_2_TO_4,
                    5: DrinkingFrequency.WEEKLY_2_TO_3,
                    6: DrinkingFrequency.WEEKLY_4_OR_MORE,
                }
            )

            amount_map = {1: 1.5, 2: 3.5, 3: 5.5, 4: 8, 5: None}

            def _convert_amount(amount: int) -> None:
                mask = current_mask & (df["drinking_amount_per_session"] == amount)
                if amount in [1, 2, 3, 4]:
                    df.loc[mask, "drinking_amount_per_session"] = amount_map[amount]
                if amount == 5:
                    if df["drinking_amount_per_session2"].isna().all():
                        df.loc[mask, "drinking_amount_per_session"] = 10
                    else:
                        mask2 = (
                            mask
                            & (~df["drinking_amount_per_session2"].isin([888, 999]))
                            & (df["drinking_amount_per_session2"].notna())
                        )
                        df.loc[mask2, "drinking_amount_per_session"] = df.loc[mask2, "drinking_amount_per_session2"]

                        # 보조 문항이 결측이거나 888/999인 경우는 10으로 대체
                        df.loc[mask & ~mask2, "drinking_amount_per_session"] = 10

            for amount in amount_map.keys():
                _convert_amount(amount)

            # 8.비해당 또는 9.모름, 무응답 -> 결측치 처리
            missing_mask = df["drinking_experience"].isin([8, 9]) | (df["drinking_frequency"].isin([8, 9]))
            df.loc[missing_mask, ["drinking_experience", "drinking_frequency", "drinking_amount_per_session"]] = np.nan
        return df

    @staticmethod
    def _clean_diagnosis_prevalence_vars(df: pd.DataFrame) -> pd.DataFrame:
        """
        의사 진단 여부(dg)를 바탕으로 설문 건너뜀(Skip logic)에 의해
        비해당(8)으로 처리된 유병 여부(pr)를 0으로 보정하고 결측치를 처리함.
        """
        if "hypertension_prevalence" in df.columns and "has_hypertension_diagnosis" in df.columns:
            mask = df["has_hypertension_diagnosis"] == 0
            df.loc[mask, "hypertension_prevalence"] = 0

        if "diabetes_prevalence" in df.columns and "has_diabetes_diagnosis" in df.columns:
            mask = df["has_diabetes_diagnosis"] == 0
            df.loc[mask, "diabetes_prevalence"] = 0

            # 이제 pr 변수에 남아있는 8이나 9는 진짜 결측치이므로 NaN 처리
        for col in ["hypertension_prevalence", "diabetes_prevalence"]:
            if col in df.columns:
                df.loc[df[col].isin([8, 9]), col] = np.nan

        return df

    @staticmethod
    def _clean_urine_status_vars(df: pd.DataFrame) -> pd.DataFrame:
        """
        요단백/요당 검사 결과 매핑 (UrineProteinStatus, UrineGlucoseStatus Enum 대응)
        """
        status_map = {
            0: UrinalysisStatus.NEGATIVE,
            1: UrinalysisStatus.TRACE,
            2: UrinalysisStatus.POSITIVE_1,
            3: UrinalysisStatus.POSITIVE_2,
            4: UrinalysisStatus.POSITIVE_3,
            5: UrinalysisStatus.POSITIVE_4,
        }
        for col in ["urine_protein", "urine_glucose"]:
            if col in df.columns:
                df[col] = df[col].map(status_map)

        return df

    @staticmethod
    def _add_derived_fasting_state(df: pd.DataFrame) -> pd.DataFrame:
        """
        공복시간을 기준으로 공복 검사 여부를 추가함.
        8시간이상이면 1
        미만이면 0
        """
        mask = df["fasting_time"] >= 8
        df.loc[mask, "fasting_state"] = 1
        df.loc[~mask, "fasting_state"] = 0
        return df

    @staticmethod
    def _drop_unperformed_blood_test_rows(df: pd.DataFrame) -> pd.DataFrame:
        """
        혈액검사가 수행되지 않은 행을 제거함.
        """
        check_cols = [
            "fbs",
            "hba1c",
            "total_cholesterol",
            "hdl",
            "triglyceride",
            "ldl",
            "ast",
            "alt",
            "creatinine",
        ]
        mask = df[check_cols].notna().any(axis=1)
        return df.loc[mask].copy()
