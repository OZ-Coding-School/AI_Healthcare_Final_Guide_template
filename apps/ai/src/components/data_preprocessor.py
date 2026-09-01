from pathlib import Path

import numpy as np
import pandas as pd

from src.enums import (
    DrinkingAmount,
    DrinkingFrequency,
    LifetimeDrinkingExperience,
    ModelType,
    SmokingStatus,
    UrinalysisStatus,
)
from src.knhanes_preprocessing_configs import KNHANES_VARIABLES_CONFIG_MAP, MODEL_VARIABLES_MAP

DataUseCase = ModelType


class KnhanesPreprocessor:
    def __init__(
        self,
        use_case: DataUseCase,
        output_dir: Path,
    ) -> None:
        self.use_case = use_case
        self.vars_config_map = KNHANES_VARIABLES_CONFIG_MAP
        self.usable_vars = MODEL_VARIABLES_MAP["common"] + MODEL_VARIABLES_MAP[self.use_case]
        self.output_dir: Path = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        데이터 전처리를 수행하는 함수.
        입력 데이터프레임(df)에서 데이터 목적에따라
        1. 필요한 변수만 추출
        2. 컬럼명 한글표기 변환
        3. 타겟 변수가 결측인 행 제거
        4. 데이터 정제
        5. 파생 변수 생성
        이 단계들을 순차적으로 수행한 후 전처리된 데이터프레임을 반환한다.
        """
        # 1. 데이터 활용 목적에 따라 필요한 변수만 추출
        processed_df = self._extract_usable_vars_from_origin_df(df)

        # 2. 컬럼명 변경 (KNHANES 변수명 -> 식별 가능한 한국어 라벨 필드명)
        processed_df = self._convert_variables_name_to_label(processed_df)

        # 3. 미성년자로 구분되는 행 모두 제거
        processed_df = self._delete_minor_rows(processed_df)

        # 4. 데이터 정제 작업(인코딩 적용, 도메인 로직에 따른 처리)
        processed_df = self._clean_data(processed_df)

        # 5. 파생 변수 생성
        processed_df = self._add_derived_features(processed_df)

        return processed_df

    def save(self, processed_df: pd.DataFrame) -> None:
        processed_df.to_parquet(self.output_dir / f"{self.use_case}.parquet", index=False)

    def _extract_usable_vars_from_origin_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터프레임에서 데이터의 활용 목적(당뇨 위험도 진단, 고혈압 위험도 진단)에 따라
        사용할 수 있는 변수만 추출하여 별도의 데이터프레임으로 반환합니다.
        """
        return df.reindex(columns=self.usable_vars).copy()

    def _delete_minor_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        미성년자로 구분되는 행을 제거합니다.
        """
        if "나이" in df.columns:
            return df[df["나이"] >= 19].copy()
        return df

    def _convert_variables_name_to_label(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        사용 가능한 변수의 컬럼명을 식별 가능한 한국어 라벨로 변경합니다.
        """
        variables_name_label_map = {
            var["name"]: var["label"] for var in self.vars_config_map if var["name"] in df.columns
        }

        return df.rename(columns=variables_name_label_map)

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        데이터 정제 작업을 수행하는 메서드입니다. 입력된 데이터프레임에 대해 다양한 정제 작업을
        순차적으로 적용하여 결과 데이터를 반환합니다.

        1. 성별 변수 인코딩
        2. 질병 여부 변수 정제
        3. 흡연 관련 변수 정제
        4. 음주량 관련 변수 정제
        5. 소변 검사 결과 상태 변수 정제
        6. 가족력 변수 정제
        """
        df = self._encode_gender(df)
        df = self._clean_has_disease_vars(df)
        df = self._clean_smoking_vars(df)
        df = self._clean_drinking_vars(df)
        df = self._encode_urinalysis_status_vars(df)
        df = self._clean_family_history_vars(df)

        return df

    def _add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        데이터프레임에 파생 변수를 추가하는 함수.
        이 함수는 BMI 필드와 가족력 필드를 데이터프레임에 추가합니다.
        """
        df = self._add_bmi_field(df)
        df = self._add_family_history_field(df)
        return df

    @staticmethod
    def _encode_gender(df: pd.DataFrame) -> pd.DataFrame:
        """
        성별 인코딩 처리 함수
        1(남) -> M,
        2(여) -> F
        """
        var_name = "성별"
        df[var_name] = df[var_name].map({1: "M", 2: "F"}).astype("category")
        return df

    @staticmethod
    def _clean_smoking_vars(df: pd.DataFrame) -> pd.DataFrame:
        """
        흡연 관련 변수 인코딩 및 결측치 처리 함수
        """
        smoking_amount = "하루평균 담배 흡연량"
        smoking_status = "현재 흡연 여부"

        exist_smoking_status_var = smoking_status in df.columns
        if exist_smoking_status_var:
            df[smoking_status] = (
                df[smoking_status]
                .map(
                    {
                        1: SmokingStatus.CURRENT,
                        2: SmokingStatus.CURRENT,
                        3: SmokingStatus.FORMER,
                        8: SmokingStatus.NEVER,
                        9: np.nan,
                    }
                )
                .astype("category")
            )

        if smoking_amount in df.columns:
            # 999 로 응답한 경우는 흡연 중이라고 대답했지만 몇개비 피는지 응답하지 않은 경우
            mask = df[smoking_amount].eq(999)
            df.loc[mask, smoking_amount] = np.nan

            # 888 로 응답한 경우는 현재 흡연중이지 않은 상태로 0개비로 설정
            mask = df[smoking_amount].eq(888)
            df.loc[mask, smoking_amount] = 0
        return df

    @staticmethod
    def _clean_drinking_vars(df: pd.DataFrame) -> pd.DataFrame:
        """
        음주 관련 변수 인코딩 및 결측치 처리 함수
        """
        drinking_experience = "평생음주경험"
        drinking_frequency = "1년간 음주빈도"
        drinking_amount_per_session = "한 번에 마시는 음주량"

        if drinking_experience in df.columns:
            df[drinking_experience] = (
                df[drinking_experience]
                .map(
                    {
                        1: LifetimeDrinkingExperience.N,
                        2: LifetimeDrinkingExperience.Y,
                        8: LifetimeDrinkingExperience.N,
                        9: np.nan,
                    }
                )
                .astype("category")
            )

        if drinking_frequency in df.columns:
            df[drinking_frequency] = (
                df[drinking_frequency]
                .map(
                    {
                        1: DrinkingFrequency.NEVER,
                        2: DrinkingFrequency.LESS_THAN_MONTHLY,
                        3: DrinkingFrequency.MONTHLY,
                        4: DrinkingFrequency.MONTHLY_2_TO_4,
                        5: DrinkingFrequency.WEEKLY_2_TO_3,
                        6: DrinkingFrequency.WEEKLY_4_OR_MORE,
                        8: DrinkingFrequency.NEVER,
                        9: np.nan,
                    }
                )
                .astype("category")
            )

        if drinking_amount_per_session in df.columns:
            df[drinking_amount_per_session] = (
                df[drinking_amount_per_session]
                .map(
                    {
                        1: DrinkingAmount.ONE_TO_TWO,
                        2: DrinkingAmount.THREE_TO_FOUR,
                        3: DrinkingAmount.FIVE_TO_SIX,
                        4: DrinkingAmount.SEVEN_TO_NINE,
                        5: DrinkingAmount.MORE_THAN_10,
                        8: DrinkingAmount.ZERO,
                        9: np.nan,
                    }
                )
                .astype("category")
            )

        return df

    def _encode_urinalysis_status_vars(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터프레임에서 소변 검사 상태 관련 변수들을 인코딩합니다.
        """
        urinalysis_status_vars = ["요당", "요단백"]
        for var_name in urinalysis_status_vars:
            if var_name in df.columns:
                df[var_name] = (
                    df[var_name]
                    .map(
                        {
                            0: UrinalysisStatus.NEGATIVE,
                            1: UrinalysisStatus.TRACE,
                            2: UrinalysisStatus.POSITIVE_1,
                            3: UrinalysisStatus.POSITIVE_2,
                            4: UrinalysisStatus.POSITIVE_3,
                            5: UrinalysisStatus.POSITIVE_4,
                        }
                    )
                    .astype("category")
                )

        return df

    def _clean_family_history_vars(self, df: pd.DataFrame) -> pd.DataFrame:
        family_history_vars = [
            "당뇨병 가족력(부)",
            "당뇨병 가족력(모)",
            "당뇨병 가족력(형제자매)",
            "고혈압 가족력(부)",
            "고혈압 가족력(모)",
            "고혈압 가족력(형제자매)",
        ]
        val_map = {
            0: "N",
            1: "Y",
            9: "UNKNOWN",
            np.nan: "UNKNOWN",
        }
        for var_name in family_history_vars:
            if var_name in df.columns:
                if "형제자매" in var_name:
                    val_map[8] = "NOT_APPLICABLE"
                df[var_name] = df[var_name].map(val_map).astype("category")

        return df

    def _clean_has_disease_vars(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터 프레임에서 질병 관련 변수를 정리하고 타깃 변수 기준으로 NaN 값을 제거한 데이터 프레임을 반환합니다.

        이 메서드는 특정 병력 관련 변수에 대해 사전 정의된 값 변환 규칙을 적용합니다. 타깃 변수에 NaN 값을
        포함한 행은 제거되며, 인덱스는 재설정됩니다.
        """
        has_disease_vars = ["당뇨병 유병 여부", "고혈압 유병 여부"]
        target_var = "당뇨병 유병 여부" if self.use_case == ModelType.DIABETES_RISK else "고혈압 유병 여부"

        for var_name in has_disease_vars:
            if var_name in df.columns:
                if var_name == target_var:
                    df[var_name] = df[var_name].map({0: 0, 1: 1, 8: 0, 9: np.nan})
                # 9(모른다고 답한경우)를 "UNKNOWN"으로 변환
                else:
                    df[var_name] = (
                        df[var_name]
                        .map(
                            {
                                0: "N",
                                1: "Y",
                                8: "N",
                                9: "UNKNOWN",
                            }
                        )
                        .astype("category")
                    )

        # 타깃 변수에 NaN 값이 있는 행을 제거하고 int형으로 변환 후 인덱스를 재설정
        df = df.dropna(subset=[target_var]).reset_index(drop=True)
        df[target_var] = df[target_var].astype(int)

        return df

    @staticmethod
    def _add_bmi_field(df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터프레임에 BMI(Body Mass Index) 필드를 추가하거나
        누락된 값을 계산하여 채워주는 정적 메서드입니다.

        BMI는 체중(kg)을 키의 제곱(m^2)으로 나눈 값으로 계산됩니다.
        주어진 데이터프레임에 '키'(cm)와 '체중'(kg) 컬럼이 존재해야 계산할 수 있으며,
        BMI 컬럼이 이미 존재하는 경우 누락된 값만 계산하여 채웁니다.
        """
        bmi = "BMI"
        height = "키"
        weight = "체중"
        if bmi not in df.columns or df[bmi].isnull().any():
            if height in df.columns and weight in df.columns:
                # height(cm) -> m
                h_m = df[height] / 100
                calculated_bmi = df[weight] / (h_m**2)
                if bmi in df.columns:
                    df[bmi] = df[bmi].fillna(calculated_bmi)
                else:
                    df[bmi] = calculated_bmi

        return df

    def _add_family_history_field(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        주어진 데이터프레임에 가족력 관련 필드를 추가하는 함수.

        이 함수는 특정 조건에 따라 새로운 파생 컬럼 (derived_field_name)을 생성하고,
        기존의 컬럼 값을 기반으로 새 컬럼 값을 계산합니다. 데이터프레임에
        필요한 컬럼이 없으면 KeyError를 방지합니다.
        """
        field_base = "당뇨병" if self.use_case == ModelType.DIABETES_RISK else "고혈압"
        derived_field_name = f"{field_base} 가족력 보유 여부"

        f_father = f"{field_base} 가족력(부)"
        f_mother = f"{field_base} 가족력(모)"
        f_sibling = f"{field_base} 가족력(형제자매)"

        if derived_field_name not in df.columns:
            # 컬럼 존재 여부 체크로 KeyError 방지
            target_cols = [c for c in [f_father, f_mother, f_sibling] if c in df.columns]
            if target_cols:
                # 하나라도 Y이면 1
                has_y = df[target_cols].eq("Y").any(axis=1)
                # 하나라도 UNKNOWN이면 UNKNOWN
                has_unknown = df[target_cols].eq("UNKNOWN").any(axis=1)
                df[derived_field_name] = "0"
                df.loc[has_unknown, derived_field_name] = "UNKNOWN"
                df.loc[has_y, derived_field_name] = "1"
                df[derived_field_name] = df[derived_field_name].astype("category")
        return df
