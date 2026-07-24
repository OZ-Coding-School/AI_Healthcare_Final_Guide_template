from pathlib import Path

import joblib

from core.utils.model_train import ModelBundle


class ModelLoader:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path

    def load(self) -> ModelBundle:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        bundle = joblib.load(self.model_path)

        return ModelBundle(
            model=bundle["model"],
            preprocessor=bundle["preprocessor"],
            feature_names=bundle["feature_names"],
        )
