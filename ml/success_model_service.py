import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from ml.success_features import APP_FEATURES, map_success_features

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = APP_FEATURES


class SuccessModelService:
    def __init__(self, model_path: Path, metrics_path: Path):
        self.model_path = model_path
        self.metrics_path = metrics_path
        self.model = None
        self.metrics = {}
        self.feature_columns = list(APP_FEATURES)
        self.threshold = 0.5
        self.model_version = None
        self.trained_at = None
        self.feature_metadata = {}
        self._load()

    def _load(self):
        self.model = None
        self.metrics = {}
        self.feature_columns = list(APP_FEATURES)
        self.threshold = 0.5
        self.model_version = None
        self.trained_at = None
        self.feature_metadata = {}

        if self.metrics_path.exists():
            try:
                with open(self.metrics_path, "r", encoding="utf-8") as handle:
                    self.metrics = json.load(handle)
            except Exception as exc:
                logger.error("Error loading success model metrics: %s", exc)
                self.metrics = {}

        artifact = None
        if self.model_path.exists():
            try:
                artifact = joblib.load(self.model_path)
            except Exception as exc:
                logger.error("Error loading success model: %s", exc)

        if artifact is None:
            return

        if isinstance(artifact, dict):
            self.model = artifact.get("model")
            artifact_columns = artifact.get("feature_columns")
            self.threshold = float(artifact.get("threshold", self.threshold))
            self.model_version = artifact.get("model_version")
            self.trained_at = artifact.get("trained_at")
        else:
            self.model = artifact
            artifact_columns = getattr(artifact, "feature_names_in_", None)

        if self.model is None:
            return

        expected_columns = list(APP_FEATURES)
        if artifact_columns is None:
            logger.error(
                "Success model has no feature schema; disabling estimates until retrained."
            )
            self.model = None
            return

        artifact_columns = [str(column) for column in artifact_columns]
        if artifact_columns != expected_columns:
            logger.error(
                "Success model feature schema mismatch. Expected %s, got %s. "
                "Disabling estimates until retrained.",
                expected_columns,
                artifact_columns,
            )
            self.model = None
            return

        metrics_columns = self.metrics.get("feature_columns")
        if metrics_columns is not None and list(metrics_columns) != expected_columns:
            logger.error(
                "Success metrics feature schema mismatch. Disabling estimates until retrained."
            )
            self.model = None
            return

        self.feature_columns = expected_columns
        if "decision_threshold" in self.metrics:
            self.threshold = float(
                self.metrics["decision_threshold"].get("selected", self.threshold)
            )
        self.model_version = self.model_version or self.metrics.get("model_version")
        self.trained_at = self.trained_at or self.metrics.get("trained_at")
        self.feature_metadata = self.metrics.get("feature_metadata", {})
        logger.info(
            "Loaded success model %s with threshold %.4f from %s",
            self.model_version or "(unknown version)",
            self.threshold,
            self.model_path,
        )

    @property
    def is_available(self):
        return self.model is not None

    def map_features(self, user_profile: dict, business_item: dict) -> dict:
        return map_success_features(user_profile, business_item)

    def predict_success_scores(self, user_profile: dict, businesses: list) -> list:
        if self.model is None or not businesses:
            return [None] * len(businesses)

        try:
            rows = [self.map_features(user_profile, business) for business in businesses]
            frame = pd.DataFrame(rows, columns=self.feature_columns)
            if list(frame.columns) != self.feature_columns:
                raise ValueError("Success feature frame does not match model schema.")
            if frame.isnull().any().any():
                raise ValueError("Success feature frame contains null values.")
            if not hasattr(self.model, "predict_proba"):
                raise ValueError("Success model does not expose predict_proba.")
            probabilities = self.model.predict_proba(frame)[:, 1]
            return [round(float(probability), 4) for probability in probabilities]
        except Exception as exc:
            logger.error("Inference error in success model batch: %s", exc)
            return [None] * len(businesses)
