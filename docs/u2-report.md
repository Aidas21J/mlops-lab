# U2 Report: Training with MLflow and hosting in the cluster

## 1. Architecture

```text
 laptop                                  Kind cluster 'mlops-cluster' / namespace mlops-lab
 ------                                  ---------------------------------------------------
 helm upgrade train ----------------->   Job train-<rev>  (image sentiment-trainer:sha-<commit>)
 (infra/job-chart)                         ConfigMap train-params  -> /config/params.yaml
                                           ConfigMap mlflow-config -> MLFLOW_TRACKING_URI
                                           Secret mlflow-credentials -> user / password
                                           bootstrap -> prepare -> train (Optuna HPO) -> evaluate
                                                         -> gate  -> promote (@champion)
                                              |  HTTP (tracking + artifact proxy)
                                              v
 browser :5005 ------------------------>  MLflow server (basic-auth) --> PostgreSQL (runs, registry)
                                                         \--> PVC mlflow-artifacts-pvc (model files)
                                              ^
                                              | models:/sentiment-analyzer@champion (at startup)
 curl :8008 --------------------------->  Deployment inference-server (FastAPI) / Service NodePort 30001

 GitHub Actions (ci.yml): ruff + pytest -> build & push images to GHCR (sha-<commit>)
```

The cluster and MLflow come from the U1 stack (Terraform + Helm, `infra/`). U2 workloads are the training Job (Helm chart `infra/job-chart`) and the inference Deployment and Service (`k8s/`). MLflow serves artifacts itself (`--serve-artifacts`), so pods and the laptop never write to the artifact volume directly.

## 2. What was done, per requirement

| Req | Implementation |
|---|---|
| R1 | `src/train.py`: Optuna study with 8 nested trial runs under a parent run; per-epoch `train_loss` / `val_accuracy` (`step`); system metrics (`log_system_metrics=True`); `log_input` with dataset digest; seed and `git_commit` tags; model logged with signature and pinned pip requirements |
| R2 | `log_model(..., registered_model_name="sentiment-analyzer")`; `scripts/gate.py promote` sets `@champion`; `src/app.py` loads `models:/sentiment-analyzer@champion` |
| R3 | `infra/job-chart`: Job + ConfigMaps; credentials from a Secret created with `kubectl`; Job ends `Completed` and the run is visible in the UI |
| R4 | FastAPI in a Deployment + Service with readiness (`/health`) and liveness (`/ping`) probes |
| R5 | `.github/workflows/ci.yml`: ruff, pytest, build and push of two images tagged `sha-<commit>` |
| R6 | Quality gate (`scripts/gate.py gate`) inside the Job and a rollback command, see section 4 and the deviation note below |
| R7 | `docs/requirements.md` v1.6 with measured values |

## 3. Measurements

| Metric | Value |
|---|---|
| p95 latency of `/predict` (100 sequential requests) | 8.03 ms |
| p50 latency | 5.53 ms |
| Throughput (10 concurrent clients) | 200 req/s |
| Model size | 1.05 KB |
| Training Job peak CPU / RAM | 0.609 core(s) / 225 MB |
| Job duration (8 trials) | 1.8 min |

Raw load test output: `docs/loadtest.json`.

## 4. Deviations and limitations

* **CD is not a GitHub workflow.** The cluster and MLflow run on a local machine. GitHub-hosted runners cannot reach them, and a self-hosted runner was rejected for security reasons (it would run repository workflow code on the development laptop). The CD chain therefore runs inside the cluster as the training Job (train -> evaluate -> gate -> promote), followed by a manual `kubectl apply` of the manifests with the new image tag. CI (lint, tests, image build and push) runs on GitHub.
* Image tags in `k8s/deployment.yaml` are updated by hand after CI publishes a new image.
* Extended tasks E1–E5 of U2 were not done. (E1 and E3 of U1 were: MLflow basic-auth and Terraform/Helm.)
* GHCR packages must be public (or loaded with `kind load docker-image`) for the cluster to pull them.
