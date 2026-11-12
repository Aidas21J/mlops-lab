# Sentiment Analysis MLOps Platform

Movie-review sentiment classification with a complete MLOps path inside a local Kubernetes cluster:
**DVC** (data) -> **Optuna + MLflow** (training, nested runs) -> **MLflow Model Registry** (`@champion`) -> **Kubernetes Job** (training) -> **FastAPI** inference service -> quality gate and rollback. Infrastructure is code (**Terraform**, **Helm**, **Kind**), CI runs on **GitHub Actions**.

* U1: cluster, MLflow server (PostgreSQL + artifact PVC, basic-auth), DVC pipeline.
* U2: HPO, registry, training Job, inference API, CI, quality gate, rollback. Report: `docs/u2-report.md`, requirements: `docs/requirements.md` (v1.6).

---

## Architecture

```text
 laptop                               Kind cluster 'mlops-cluster' / namespace mlops-lab
 ------                               ---------------------------------------------------
 helm upgrade train  --------------->  Job train-<rev>: bootstrap -> prepare -> train (Optuna)
 (infra/job-chart)                                       -> evaluate -> gate -> promote
                                           | tracking + artifacts over HTTP
 browser :5005  -------------------->  MLflow server (basic-auth) --> PostgreSQL (runs, registry)
                                                       \--> PVC mlflow-artifacts-pvc (models)
                                           ^ models:/sentiment-analyzer@champion
 curl :8008  ----------------------->  Deployment inference-server (FastAPI) / Service NodePort 30001
```

---

## Prerequisites

Docker, [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.0, `kind`, `kubectl`, `helm`, and **Python 3.12** (newer versions lack prebuilt wheels for some DVC dependencies).

---

## 1. Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Create `infra/terraform.tfvars` (git-ignored; the password needs 12+ characters):

```hcl
mlflow_admin_password = "SuperAdminPassword123!"
flask_secret_key      = "a-very-secret-flask-key"
mlflow_host_port      = 5005
inference_host_port   = 8008
```

Create the cluster and the MLflow stack:

```bash
cd infra && terraform init && terraform apply -auto-approve && cd ..
```

* MLflow UI: `http://localhost:5005`, user `admin`, password from `terraform.tfvars`.
* After editing files under `infra/mlops-lab-chart/templates/`, **bump `version` in `Chart.yaml`** before `terraform apply`, otherwise Terraform sees no change.
* MLflow serves artifacts itself (`--serve-artifacts`) and allows the in-cluster hostname (`--allowed-hosts`), so Jobs and pods can log and load models.

Environment for local commands (`dvc repro`, `scripts/gate.py`):

```bash
export MLFLOW_TRACKING_URI="http://localhost:5005"
export MLFLOW_TRACKING_USERNAME="admin"
export MLFLOW_TRACKING_PASSWORD="<password from terraform.tfvars>"
```

---

## 2. Cluster configuration and secrets

```bash
kubectl apply -f k8s/configmap.yaml            # MLFLOW_TRACKING_URI=http://mlflow-service:5000
kubectl create secret generic mlflow-credentials -n mlops-lab \
  --from-literal=MLFLOW_TRACKING_USERNAME=admin \
  --from-literal=MLFLOW_TRACKING_PASSWORD='<password>'
```

The real Secret is never committed; `k8s/secret.example.yaml` only shows its shape.

---

## 3. Images

CI (`.github/workflows/ci.yml`) builds and pushes `sentiment-analyzer-api` and `sentiment-trainer` to GHCR as `sha-<commit>` on `main`. To use local builds instead:

```bash
TAG=sha-$(git rev-parse --short=8 HEAD)
docker build -f docker/Dockerfile.train --build-arg GIT_COMMIT=${TAG#sha-} -t ghcr.io/aidas21j/mlops-lab/sentiment-trainer:$TAG .
docker build -f docker/Dockerfile -t ghcr.io/aidas21j/mlops-lab/sentiment-analyzer-api:$TAG .
kind load docker-image --name mlops-cluster \
  ghcr.io/aidas21j/mlops-lab/sentiment-trainer:$TAG ghcr.io/aidas21j/mlops-lab/sentiment-analyzer-api:$TAG
```

Image sizes and the Trivy scan are in `docs/image-sizes.md`.

---

## 4. Training Job (HPO, registry, gate)

```bash
helm upgrade --install train ./infra/job-chart -n mlops-lab \
  --set image.tag=$TAG --wait --wait-for-jobs --timeout 20m
kubectl logs job/train-1 -n mlops-lab        # name = train-<helm revision>
```

The Job runs: `bootstrap.py` -> `prepare.py` -> `train.py` -> `evaluate.py` -> `gate.py gate` -> `gate.py promote`.

* `train.py` runs an Optuna study (`hpo.n_trials` nested runs under one parent run), logs per-epoch metrics, system metrics, dataset digest, seed and git commit, and registers the model as `sentiment-analyzer`.
* `gate.py gate` exits 1 if the metric is below `gate.min`, so the Job fails and **nothing is promoted**.
* `gate.py promote` sets the alias `@champion` and remembers the previous champion in a `replaced` tag.
* Parameters live in `infra/job-chart/values.yaml` (rendered into the `train-params` ConfigMap). Override them per run:

```bash
helm upgrade train ./infra/job-chart -n mlops-lab --reuse-values \
  --set params.train.hpo.n_trials=3 --wait --wait-for-jobs      # change a hyperparameter
helm upgrade train ./infra/job-chart -n mlops-lab --reuse-values \
  --set params.gate.min=0.99 --wait --wait-for-jobs             # gate blocks: Job fails (red)
```

Results: MLflow UI -> experiment `sentiment-analysis-u2` (parent run with trial runs) and Models -> `sentiment-analyzer` (alias `champion`).

---

## 5. Inference API

```bash
kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml
kubectl rollout status deployment/inference-server -n mlops-lab

curl localhost:8008/health        # {"status":"ok","model_version":"<n>"}
curl -X POST localhost:8008/predict -H "Content-Type: application/json" \
     -d '{"message": "a surprisingly moving and funny film"}'
```

The service loads `models:/sentiment-analyzer@champion` from the registry at startup. It never reads a model file from the image. After the alias changes, restart the pods:

```bash
kubectl rollout restart deployment/inference-server -n mlops-lab
```

To update the image, set the new `sha-<commit>` tag in `k8s/deployment.yaml` and `kubectl apply` it.

**Load test:** `python scripts/loadtest.py` (100 sequential requests for p95/p50, then 10 concurrent clients for throughput) writes `docs/loadtest.json`.

---

## 6. Rollback

```bash
python scripts/gate.py rollback            # champion -> previous version (the `replaced` tag)
python scripts/gate.py rollback 3          # or an explicit version
kubectl rollout restart deployment/inference-server -n mlops-lab
curl localhost:8008/health                 # shows the rolled-back model_version
```

---

## 7. CI

`.github/workflows/ci.yml` runs on every push: `ruff check .` and `pytest` (gate logic, API with a mocked registry), then builds both images and pushes them to GHCR on `main`.

CD runs in the cluster (section 4) because GitHub-hosted runners cannot reach a local cluster; see `docs/u2-report.md`, section 5.

---

## 8. Local pipeline (without the cluster Job)

```bash
dvc pull          # data from the local DVC remote
dvc repro         # prepare -> train (HPO) -> evaluate; logs to the cluster MLflow
python scripts/gate.py gate && python scripts/gate.py promote
```

`scripts/reproduce.py <run_id>` re-creates a historic run. `scripts/three-runs.sh` is the U1 sweep over `C` and is obsolete after U2.

---

## Project structure

```text
.
├── .github/workflows/ci.yml    # lint, tests, image build and push
├── docker/                     # Dockerfile (API), Dockerfile.train (Job)
├── docs/                       # requirements.md (v1.6), u2-report.md, u1-report.md, loadtest.json
├── infra/
│   ├── main.tf                 # Terraform: Kind cluster + Helm release
│   ├── mlops-lab-chart/        # Helm chart: MLflow + PostgreSQL
│   └── job-chart/              # Helm chart: training Job + parameters
├── k8s/                        # configmap, deployment, service, secret example
├── scripts/                    # bootstrap.py, gate.py, loadtest.py, reproduce.py
├── src/                        # prepare.py, train.py, evaluate.py, app.py
├── tests/                      # pytest: gate and API
├── dvc.yaml / params.yaml
└── requirements*.txt
```

---

## Cleanup

```bash
helm uninstall train -n mlops-lab
cd infra && terraform destroy -auto-approve      # deletes the cluster AND all MLflow history
```
