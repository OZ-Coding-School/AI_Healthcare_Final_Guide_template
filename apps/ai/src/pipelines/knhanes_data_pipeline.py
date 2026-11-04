from pathlib import Path

import pandas as pd

from core.config import settings
from core.logger import configure_logger
from src.components.knhanes_multi_year_loader import KnhanesMultiYearLoader, KnhanesQualityReport

logger = configure_logger("KNHANES Pipeline")

RAW_DATA_DIR = settings.DATA_DIR / "raw" / "knhanes"
MERGED_DATA_PATH = settings.DATA_DIR / "interim" / "knhanes_2020_2024.parquet"
QUALITY_REPORT_PATH = settings.MODEL_REPORT_DIR / "knhanes_quality_report.json"


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


if __name__ == "__main__":
    run_knhanes_merge()
