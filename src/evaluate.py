import os
import json
import yaml
from pathlib import Path
import pandas as pd
import joblib
import mlflow
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def evaluate() -> None:
    with open("params.yaml") as f:
        params = yaml.safe_load(f)["train"]

    DATA_DIR = params["data"]["processed_data_dir"]
    MODEL_DIR = params["model_dir"]
    METRICS_DIR = params["metrics_dir"]

    test_file = os.path.join(DATA_DIR, "test.csv")
    model_file = os.path.join(MODEL_DIR, "model.pkl")

    test_df = pd.read_csv(test_file)
    test_input, test_expected = test_df["text"], test_df["label"]
    
    model = joblib.load(model_file)
    preds = model.predict(test_input)

    metrics = {
        "eval-accuracy": accuracy_score(test_expected, preds),
        "eval-precision": precision_score(test_expected, preds),
        "eval-recall": recall_score(test_expected, preds),
        "eval-f1": f1_score(test_expected, preds, average="weighted"),
    }
    
    print(f"Metrics: {metrics}")
    
    os.makedirs(METRICS_DIR, exist_ok=True)
    metrics_file = os.path.join(METRICS_DIR, "scores.json")

    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=4)
        print(f"Metrics saved to {metrics_file}.")
        
    try:
        run_id = Path(os.path.join(MODEL_DIR, "run_id.txt")).read_text().strip()
        with mlflow.start_run(run_id=run_id):
            mlflow.log_metrics(metrics)
    except Exception as e:
        print(f"Warning: eval metrics not attached to the training run ({e})")


if __name__ == "__main__":
    evaluate()
