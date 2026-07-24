from pathlib import Path

import pandas as pd
from pyreadstat import ReadstatError

from core import settings
from core.enums import DataPurposeType, ModelAlgorithm
from core.utils import DataLoader, KnhanesPreprocessor
from core.utils.model_evaluation_reporter import ModelEvaluationReporter
from core.utils.model_evaluator import ModelEvaluator
from core.utils.model_train import BinaryClassificationModelTrainer


def get_knhanes_raw_data_file_paths() -> list[Path]:
    data_dir = settings.DATA_DIR / "raw/knhanes"
    return [data_dir / file.name for file in data_dir.glob("*.sas7bdat")]


if __name__ == "__main__":
    data_loader = DataLoader()
    raw_dataframes = []
    for file_path in get_knhanes_raw_data_file_paths():
        try:
            raw_dataframes.append(data_loader.load(file_path).df)
        except (AttributeError, FileNotFoundError, ReadstatError) as e:
            print(f"Error: {e}\nskipping {file_path}..")
            continue

    df = pd.concat(raw_dataframes, ignore_index=True)

    for purpose in [DataPurposeType.DIABETES_DIAGNOSIS, DataPurposeType.HYPERTENSION_DIAGNOSIS]:
        common_preprocessor = KnhanesPreprocessor(purpose=purpose)
        processed_split_data = common_preprocessor.preprocess(df)
        for algorithm in ModelAlgorithm:
            for use_smote in [True, False]:
                model_trainer = BinaryClassificationModelTrainer(
                    x_train=processed_split_data.x_train,
                    y_train=processed_split_data.y_train,
                    output_filename=purpose.value,
                    algorithm=algorithm,
                    use_smote=use_smote,
                )
                model_bundle = model_trainer.train()
                print(f"[{purpose.value}] {algorithm} training... / SMOTE: {use_smote}")

                model_evaluator = ModelEvaluator(
                    model=model_bundle.model,
                    preprocessor=model_bundle.preprocessor,
                    x_test=processed_split_data.x_test,
                    y_test=processed_split_data.y_test,
                )
                evaluation_result = model_evaluator.evaluate()

                output_basename = f"{purpose.value}_{algorithm}"
                if use_smote:
                    output_basename += "_smote"
                reporter = ModelEvaluationReporter(
                    output_basename=output_basename,
                )
                reporter.save_report(evaluation_result)
