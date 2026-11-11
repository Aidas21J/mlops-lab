import os
import optuna
import subprocess
from pathlib import Path
import yaml
import pandas as pd
import numpy as np
import joblib
import mlflow
from mlflow.models import infer_signature
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, log_loss


PARAMS_PATH = os.getenv("PARAMS_PATH", "params.yaml")
NAME = "sentiment-analyzer"


def git_commit() -> str:
    if os.getenv("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"]

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


def fit(texts, y, max_features, alpha, epochs, seed, val=None, log_steps=False):
    vec = TfidfVectorizer(max_features=max_features, ngram_range=(1, 2))
    X = vec.fit_transform(texts)
    clf = SGDClassifier(loss="log_loss", alpha=alpha, random_state=seed)
    for epoch in range(epochs):
        clf.partial_fit(X, y, classes=[0, 1])
        if log_steps:
            mlflow.log_metric("train_loss", log_loss(y, clf.predict_proba(X)), step=epoch)
            if val is not None:
                mlflow.log_metric("val_accuracy",
                    accuracy_score(val[1], clf.predict(vec.transform(val[0]))), step=epoch)
    return Pipeline([("tfidf", vec), ("clf", clf)])


def train() -> None:
    with open(PARAMS_PATH) as f:
        params = yaml.safe_load(f)["train"]
    
    DATA_DIR = params["data"]["processed_data_dir"]
    RAW_DIR = params["data"]["raw_data_dir"]
    RANDOM_STATE = params["random_state"]
    EPOCHS = params["hpo"]["epochs"]
    N_TRIALS = params["hpo"]["n_trials"]
    MODEL_DIR = params["model_dir"]

    np.random.seed(RANDOM_STATE)

    train_data_filename = os.path.join(DATA_DIR, "train.csv")
    validation_data_filename = os.path.join(DATA_DIR, "validation.csv")

    train_df = pd.read_csv(train_data_filename)
    train_input, train_expected = train_df["text"], train_df["label"]

    validation_df = pd.read_csv(train_data_filename)
    validation_input, validation_expected = validation_df["text"], validation_df["label"]

    mlflow.set_experiment("sentiment-analysis-u2")
    
    with mlflow.start_run(run_name="hpo-parent", log_system_metrics=True) as run:
        mlflow.log_params(pd.json_normalize(params, sep=".").iloc[0].to_dict())

        mlflow.set_tags({
            "git_commit": git_commit(),
            "dvc_raw_md5": dvc_md5(Path(os.path.join(RAW_DIR, "train.csv.dvc"))),
            "model_family": "TF-IDF + SGDClassifier (log loss)",
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

        def objective(trial):
            with mlflow.start_run(run_name=f"trial-{trial.number}", nested=True):
                mf = trial.suggest_categorical("max_features", [5000, 10000, 20000])
                a = trial.suggest_float("alpha", 1e-6, 1e-2, log=True)
                mlflow.log_params({"max_features": mf, "alpha": a})
                m = fit(train_input, train_expected, mf, a, EPOCHS, RANDOM_STATE, val=(validation_input, validation_expected), log_steps=True)
                acc = accuracy_score(validation_expected, m.predict(validation_input))
                mlflow.log_metric("validation_accuracy_final", acc)
                return acc

        study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE))
        study.optimize(objective, n_trials=N_TRIALS)
        mlflow.log_params({f"best_{k}": v for k, v in study.best_params.items()})

        model = fit(
            train_input,
            train_expected,
            study.best_params["max_features"],
            study.best_params["alpha"],
            EPOCHS,
            RANDOM_STATE,
            val=(validation_input, validation_expected),
            log_steps=True
        )
        sig = infer_signature(train_input.head(5).to_frame(), model.predict(train_input.head(5)))
        info = mlflow.sklearn.log_model(
            sk_model=model,
            name=NAME,
            registered_model_name=NAME,
            signature=sig,
            input_example=train_input.head(3).to_frame(),
            pip_requirements=["scikit-learn==1.9.1", "pandas"]
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
