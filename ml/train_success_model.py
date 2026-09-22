import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import train_success_models

def train_success_classifier(data_path=None, model_dir=None):
    res = train_success_models.train()
    if res:
        return {"Logistic Regression": res["test_metrics"]}
    return None

if __name__ == "__main__":
    train_success_classifier()
