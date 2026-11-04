import json
from pathlib import Path

import pandas as pd

from core.config import settings
from core.logger import configure_logger
from src.components.data_preprocessor import KnhanesPreprocessor
from src.components.knhanes_label_builder import KnhanesLabelBuilder, KnhanesLabelReport
from src.components.knhanes_multi_year_loader import KnhanesMultiYearLoader, KnhanesQualityReport
from src.enums import ModelType

logger = configure_logger("KNHANES Pipeline")

RAW_DATA_DIR = settings.DATA_DIR / "raw" / "knhanes"
MERGED_DATA_PATH = settings.DATA_DIR / "interim" / "knhanes_2020_2024.parquet"
QUALITY_REPORT_PATH = settings.MODEL_REPORT_DIR / "knhanes_quality_report.json"
LABELED_DATA_DIR = settings.DATA_DIR / "interim" / "labeled"
LABEL_REPORT_PATH = settings.MODEL_REPORT_DIR / "knhanes_label_report.json"
PREPROCESSED_DATA_DIR = settings.DATA_DIR / "interim" / "preprocessed"


def run_knhanes_merge(
    raw_data_dir: Path = RAW_DATA_DIR,
    merged_data_path: Path = MERGED_DATA_PATH,
    quality_report_path: Path = QUALITY_REPORT_PATH,
    strict_codes: bool = False,
) -> tuple[pd.DataFrame, KnhanesQualityReport]:
    merged_df, report = KnhanesMultiYearLoader(raw_data_dir, strict_codes=strict_codes).load()

    merged_data_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_parquet(merged_data_path, index=False)
    report.save(quality_report_path)

    logger.info("Merged %d rows into %s", len(merged_df), merged_data_path)
    logger.info("Saved quality report to %s", quality_report_path)
    return merged_df, report


def run_knhanes_labeling(
    merged_data_path: Path = MERGED_DATA_PATH,
    labeled_data_dir: Path = LABELED_DATA_DIR,
    label_report_path: Path = LABEL_REPORT_PATH,
    strict_official_match: bool = True,
) -> dict[ModelType, tuple[pd.DataFrame, KnhanesLabelReport]]:
    if not merged_data_path.exists():
        raise FileNotFoundError(f"Merged KNHANES data not found: {merged_data_path}")

    merged_df = pd.read_parquet(merged_data_path)
    builder = KnhanesLabelBuilder(strict_official_match=strict_official_match)
    results = {model_type: builder.build(merged_df, model_type) for model_type in ModelType}

    labeled_data_dir.mkdir(parents=True, exist_ok=True)
    for model_type, (labeled_df, _) in results.items():
        labeled_df.to_parquet(labeled_data_dir / f"{model_type}.parquet", index=False)

    label_report_path.parent.mkdir(parents=True, exist_ok=True)
    label_report_path.write_text(
        json.dumps(
            {str(model_type): report.to_dict() for model_type, (_, report) in results.items()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    logger.info("Saved labeled data to %s", labeled_data_dir)
    logger.info("Saved label report to %s", label_report_path)
    return results


def run_knhanes_preprocessing(
    labeled_data_dir: Path = LABELED_DATA_DIR,
    preprocessed_data_dir: Path = PREPROCESSED_DATA_DIR,
) -> dict[ModelType, pd.DataFrame]:
    results: dict[ModelType, pd.DataFrame] = {}
    for model_type in ModelType:
        labeled_data_path = labeled_data_dir / f"{model_type}.parquet"
        if not labeled_data_path.exists():
            raise FileNotFoundError(f"Labeled KNHANES data not found: {labeled_data_path}")

        preprocessor = KnhanesPreprocessor(use_case=model_type, output_dir=preprocessed_data_dir)
        results[model_type] = preprocessor.preprocess_labeled(pd.read_parquet(labeled_data_path))

    # 모든 질환이 성공한 뒤 저장해 일부만 갱신된 상태를 남기지 않습니다.
    for model_type, preprocessed_df in results.items():
        KnhanesPreprocessor(use_case=model_type, output_dir=preprocessed_data_dir).save(preprocessed_df)

    logger.info("Saved preprocessed data to %s", preprocessed_data_dir)
    return results


if __name__ == "__main__":
    run_knhanes_merge()
    run_knhanes_labeling()
    run_knhanes_preprocessing()
