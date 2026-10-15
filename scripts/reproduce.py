import os
import argparse
import subprocess
import sys
import time
from pathlib import Path

import mlflow
import yaml

TRAIN_KEYS = {
    "random_state": int,
    "C": float,
    "max_features": int,
}


def run_command(cmd: list[str]) -> str:
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    if result.returncode != 0:
        print(f"Error when running: {cmd}", file=sys.stderr)
        if capture:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def reproduce() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--tolerance", type=float, default=0.005)
    args = ap.parse_args()

    start_time = time.time()

    run = mlflow.get_run(args.run_id)
    run_tags, run_params, run_metrics = run.data.tags, run.data.params, run.data.metrics
    commit = run_tags.get("mlflow.source.git.commit") or run_tags.get("git_commit")
    if not commit or commit == "unknown":
        sys.exit("run has no git commit tag - cannot reproduce")

    start_ref = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    ok = False
    try:
        run_command(["git", "checkout", "--quiet", commit])

        with open("params.yaml") as f:
            params = yaml.safe_load(f)

        MODEL_DIR = params["train"]["model_dir"]

        pointers = [
            str(p.relative_to(Path.cwd()))
            for p in Path().cwd().rglob("*.dvc")
            if p.is_file() and p.name != ".dvc"
        ]
        if pointers:
            run_command(["dvc", "checkout", "--force", *pointers])

        params["train"]["random_seed"] = int(run_params["random_state"])
        params["train"]["C"] = float(run_params["C"])
        params["train"]["max_features"] = int(run_params["max_features"])
        Path("params.yaml").write_text(yaml.safe_dump(params, sort_keys=False))

        run_command(["dvc", "repro", "--force"])
        new_id = Path(os.path.join(MODEL_DIR, "run_id.txt")).read_text().strip()
        new = mlflow.get_run(new_id)
        mlflow.MlflowClient().set_tag(new_id, "reproduces", args.run_id)

        print(new.data.metrics)

        ok = True
        for key in ["eval-accuracy", "eval-f1"]:
            delta = abs(new.data.metrics[key] - run_metrics[key])
            ok &= delta <= args.tolerance
            print(f"{key}: original={run_metrics[key]:.4f} reproduced={new.data.metrics[key]:.4f} delta={delta:.4f}")
    finally:
        run_command(["git", "checkout", "--quiet", "--force", start_ref])
        run_command(["dvc", "checkout", "--force"])

    print(f"{'REPRODUCED' if ok else 'MISMATCH'} in {time.time() - start_time:.2f}s -> new run {new_id}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    reproduce()
