import os
import subprocess
from pathlib import Path
import yaml
import pandas as pd
import joblib
import mlflow
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=8", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def dvc_md5(dvc_file: Path) -> str:
    try:
        return yaml.safe_load(dvc_file.read_text())["outs"][0]["md5"]
    except Exception:
        return "untracked"


def train() -> None:
    with open("params.yaml") as f:
        params = yaml.safe_load(f)["train"]
    
    DATA_DIR = params["data"]["processed_data_dir"]
    RAW_DIR = params["data"]["raw_data_dir"]
    MAX_FEATURES = params["max_features"]
    RANDOM_STATE = params["random_state"]
    C = params["C"]
    MODEL_DIR = params["model_dir"]

    train_data_filename = os.path.join(DATA_DIR, "train.csv")
    test_data_filename = os.path.join(DATA_DIR, "test.csv")

    train_df = pd.read_csv(train_data_filename)
    train_input, train_expected = train_df["text"], train_df["label"]

    mlflow.set_experiment("sentiment-analysis-cpu")
    
    with mlflow.start_run() as run:
        mlflow.log_params(params)

        mlflow.set_tags({
            "git_commit": git_commit(),
            "dvc_raw_md5": dvc_md5(Path(os.path.join(RAW_DIR, "train.csv.dvc"))),
            "model_family": "Term Frequency-Inverse Document Frequency + Logistic Regression",
        })

        mlflow.log_input(
            mlflow.data.from_pandas(
                train_df,
                source=train_data_filename,
                targets="label",
                name="train",
            ),
            context="training",
        )

        model = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=MAX_FEATURES, ngram_range=(1, 2))),
            ('clf', LogisticRegression(C=C, random_state=RANDOM_STATE))
        ])
        
        print("Training the model...")
        model.fit(train_input, train_expected)

        info = mlflow.sklearn.log_model(
            sk_model=model,
            name="sentiment-analyzer",
            pip_requirements=["scikit-learn"],
            input_example=train_input.head(3).values.tolist(),
        )

        preds = model.predict(train_input)

        metrics = {
            "train-accuracy": accuracy_score(train_expected, preds),
            "train-precision": precision_score(train_expected, preds),
            "train-recall": recall_score(train_expected, preds),
            "train-f1": f1_score(train_expected, preds, average="weighted"),
        }
        mlflow.log_metrics(metrics)

        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump(model, os.path.join(MODEL_DIR, "model.pkl"))
        Path(os.path.join(MODEL_DIR, "run_id.txt")).write_text(run.info.run_id + "\n")

        print("Model trained successfully.")
        print(f"run_id={run.info.run_id}")
        print(f"model_id={info.model_id}")


if __name__ == "__main__":
    train()
