import os
import sys
import json
import yaml
from mlflow import MlflowClient


NAME = "sentiment-analyzer"
c = MlflowClient()
params = yaml.safe_load(open(os.getenv("PARAMS_PATH", "params.yaml")))


def gate():
    metrics_path = os.path.join(params["train"]["metrics_dir"], "scores.json")
    metrics = json.load(open(metrics_path))
    key = params["gate"]["metric"]
    threshold = float(os.getenv("GATE_MIN", params["gate"]["min"]))
    print(f"{key}={metrics[key]:.4f} threshold={threshold}")
    sys.exit(0 if metrics[key] >= threshold else 1)


def promote():
    model_path = os.path.join(params["train"]["model_dir"], "run_id.txt")
    run_id = open(model_path).read().strip()
    new = next(v for v in c.search_model_versions(f"name='{NAME}'") if v.run_id == run_id)
    try:
        old = c.get_model_version_by_alias(NAME, "champion").version
        c.set_model_version_tag(NAME, new.version, "replaced", old)
    except Exception:
        pass
    c.set_registered_model_alias(NAME, "champion", new.version)
    print("champion ->", new.version)


def rollback():
    cur = c.get_model_version_by_alias(NAME, "champion")
    prev = sys.argv[2] if len(sys.argv) > 2 else cur.tags["replaced"]
    c.set_registered_model_alias(NAME, "champion", prev)
    print("champion rolled back ->", prev)


{
    "gate": gate,
    "promote": promote,
    "rollback": rollback
}[sys.argv[1]]()
