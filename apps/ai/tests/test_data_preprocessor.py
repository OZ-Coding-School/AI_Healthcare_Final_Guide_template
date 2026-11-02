from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.components.data_preprocessor import KnhanesPreprocessor
from src.enums import ModelType


@pytest.fixture
def raw_knhanes_sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sex": [1, 2, 1, 2],
            "age": [45, 50, 15, 60],  # 15세는 미성년자 필터링 대상
            "HE_ht": [170.0, 160.0, 150.0, 175.0],
            "HE_wt": [70.0, 60.0, 45.0, 80.0],
            "HE_wc": [85.0, 75.0, 60.0, 90.0],
            "HE_BMI": [np.nan, 23.4, 20.0, 26.1],
            "BD1": [2, 1, 8, 2],
            "BD1_11": [3, 1, 8, 5],
            "BD2_1": [2, 8, 8, 4],
            "BS3_1": [1, 3, 8, 2],
            "BS3_2": [10, 888, 888, 999],
            "HE_chol": [190, 210, 160, 230],
            "HE_HDL_st2": [50, 55, 60, 45],
            "HE_TG": [120, 150, 80, 180],
            "HE_ast": [25, 20, 18, 30],
            "HE_alt": [22, 18, 15, 35],
            "HE_crea": [1.0, 0.8, 0.7, 1.1],
            "HE_Upro": [0, 1, 0, 2],
            "DE1_pr": [0, 1, 0, 1],  # 당뇨 타겟
            "HE_sbp": [120, 130, 110, 140],
            "HE_dbp": [80, 85, 70, 90],
            "DI1_pr": [0, 1, 0, 1],
            "HE_DMfh1": [0, 1, 0, 9],
            "HE_DMfh2": [0, 0, 0, 1],
            "HE_DMfh3": [0, 8, 0, 1],
        }
    )


def test_knhanes_preprocessor_diabetes(raw_knhanes_sample_df, tmp_path: Path):
    preprocessor = KnhanesPreprocessor(use_case=ModelType.DIABETES_RISK, output_dir=tmp_path)
    processed_df = preprocessor.preprocess(raw_knhanes_sample_df)

    # 미성년자 1명(나이 15) 제외되어 3행이어야 함
    assert len(processed_df) == 3

    # 변수명이 한국어 라벨로 변환되었는지 확인
    assert "성별" in processed_df.columns
    assert "나이" in processed_df.columns
    assert "당뇨병 유병 여부" in processed_df.columns
    assert "BMI" in processed_df.columns
    assert "당뇨병 가족력 보유 여부" in processed_df.columns

    # 성별 인코딩 확인 (1->M, 2->F)
    assert set(processed_df["성별"].dropna().unique()).issubset({"M", "F"})

    # 결측치였던 첫 번째 행의 BMI가 계산되어 채워졌는지 확인 (70 / (1.7^2) = 24.22)
    assert not processed_df["BMI"].isnull().any()
    assert np.isclose(processed_df["BMI"].iloc[0], 70 / (1.7**2), atol=0.01)

    # Parquet 저장 확인
    preprocessor.save(processed_df)
    saved_file = tmp_path / f"{ModelType.DIABETES_RISK}.parquet"
    assert saved_file.exists()


def test_knhanes_preprocessor_drop_target_nan(raw_knhanes_sample_df, tmp_path: Path):
    df_with_target_nan = raw_knhanes_sample_df.copy()
    df_with_target_nan.loc[0, "DE1_pr"] = 9  # 모름/무응답 -> NaN 변환 후 행 삭제 대상

    preprocessor = KnhanesPreprocessor(use_case=ModelType.DIABETES_RISK, output_dir=tmp_path)
    processed_df = preprocessor.preprocess(df_with_target_nan)

    # 미성년자 제외(1명) + 타겟 결측 제외(1명) -> 총 2행
    assert len(processed_df) == 2
