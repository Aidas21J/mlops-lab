import json
import os
import sys

import yaml
from mlflow import MlflowClient

NAME = "sentiment-analyzer"


def load_params() -> dict:
    with open(os.getenv("PARAMS_PATH", "params.yaml")) as f:
        return yaml.safe_load(f)


def gate() -> bool:
    params = load_params()
    key = params["gate"]["metric"]
    threshold = float(os.getenv("GATE_MIN", params["gate"]["min"]))
    with open("metrics/scores.json") as f:
        value = json.load(f)[key]
    print(f"{key}={value:.4f} threshold={threshold}")
    return value >= threshold


def promote() -> None:
    client = MlflowClient()
    with open("models/run_id.txt") as f:
        run_id = f.read().strip()
    versions = [v for v in client.search_model_versions(f"name='{NAME}'") if v.run_id == run_id]
    if not versions:
        sys.exit(f"no registered version found for run {run_id}")
    new = versions[0]
    try:
        old = client.get_model_version_by_alias(NAME, "champion").version
        client.set_model_version_tag(NAME, new.version, "replaced", old)
    except Exception:
        pass  # first ever champion
    client.set_registered_model_alias(NAME, "champion", new.version)
    print("champion ->", new.version)


def rollback(version: str | None = None) -> None:
    client = MlflowClient()
    if version is None:
        current = client.get_model_version_by_alias(NAME, "champion")
        version = current.tags.get("replaced")
        if not version:
            sys.exit("current champion has no 'replaced' tag; pass a version explicitly")
    client.set_registered_model_alias(NAME, "champion", str(version))
    print("champion rolled back ->", version)


def main(argv: list[str]) -> None:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "gate":
        sys.exit(0 if gate() else 1)
    elif cmd == "promote":
        promote()
    elif cmd == "rollback":
        rollback(argv[2] if len(argv) > 2 else None)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
