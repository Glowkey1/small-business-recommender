from ml.train_success_model import train_success_classifier
from ml.evaluate_models import get_current_metrics

class MLService:
    @staticmethod
    def retrain_models():
        return train_success_classifier()

    @staticmethod
    def get_metrics():
        return get_current_metrics()
