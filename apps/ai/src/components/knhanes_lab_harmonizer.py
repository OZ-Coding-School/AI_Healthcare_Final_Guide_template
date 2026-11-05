import pandas as pd
from pandas.api.types import is_numeric_dtype

from src.components.knhanes_multi_year_loader import YEAR_VAR, KnhanesDataValidationError
from src.enums import ModelType
from src.knhanes_preprocessing_configs import KNHANES_VARIABLES_CONFIG_MAP, MODEL_INPUT_VARS_MAP
from src.knhanes_split_configs import LabHarmonizationRule


class KnhanesLabHarmonizer:
    def __init__(self, model_type: ModelType) -> None:
        self.model_type = model_type
        self.label_by_var_name = {var["name"]: str(var["label"]) for var in KNHANES_VARIABLES_CONFIG_MAP}

    def transform(self, df: pd.DataFrame, rules: list[LabHarmonizationRule]) -> pd.DataFrame:
        """
        전처리된 데이터의 검사값을 전환식으로 맞춥니다.
        라벨은 이미 원값으로 만들어졌으므로 바꾸지 않고, 해당 모델의 입력이 아닌 검사값은 건너뜁니다.
        """
        applicable_rules = [rule for rule in rules if rule.var_name in MODEL_INPUT_VARS_MAP[self.model_type]]
        self._validate(df, applicable_rules)

        harmonized_df = df.copy()
        for rule in applicable_rules:
            column = self.label_by_var_name[rule.var_name]
            target_rows = df[YEAR_VAR].isin(rule.years)
            harmonized_df[column] = df[column].astype(float).mask(target_rows, df[column] * rule.slope + rule.intercept)

        return harmonized_df

    def _validate(self, df: pd.DataFrame, rules: list[LabHarmonizationRule]) -> None:
        if YEAR_VAR not in df.columns or df[YEAR_VAR].isna().any():
            raise KnhanesDataValidationError(f"{self.model_type}: {YEAR_VAR} is required for lab harmonization")

        columns = [self.label_by_var_name[rule.var_name] for rule in rules]
        missing_columns = [column for column in columns if column not in df.columns]
        if missing_columns:
            raise KnhanesDataValidationError(f"{self.model_type}: missing lab columns: {missing_columns}")

        non_numeric_columns = [column for column in columns if not is_numeric_dtype(df[column])]
        if non_numeric_columns:
            raise KnhanesDataValidationError(f"{self.model_type}: lab columns must be numeric: {non_numeric_columns}")
