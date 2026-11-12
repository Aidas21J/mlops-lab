# Project Requirements: Sentiment Analysis MLOps Platform
**Document Version:** v1.6
**Project Domain:** NLP / movie-review sentiment classification (Rotten Tomatoes)
**Target Architecture:** Kind cluster (Terraform + Helm), MLflow (tracking + model registry), DVC, Kubernetes Job (training), FastAPI inference service, GitHub Actions CI

### Changelog
* **v1.1** – U1: reproducible pipeline, MLflow in the cluster (FR1–FR3, NFR1–NFR5).
* **v1.6** – U2: HPO with nested runs, model registry with `@champion`, training Job, inference API, CI, quality gate, rollback (FR4–FR8, NFR6–NFR9); inference NFRs now carry **measured** values.

---

## 1. Problem Statement
Classify movie reviews as positive or negative through a reproducible, fully tracked path: data -> training with hyperparameter search -> model registry -> training Job and inference service in the same Kubernetes cluster -> quality gate and rollback. Model quality is secondary; the flow around the model is what is evaluated.

---

## 2. Functional Requirements (FR)

* **FR1: Data version control & ingestion.** Datasets are versioned with DVC (`localremote`); the Job downloads the pinned Hugging Face commit (`train.data.commit_hash`) so it needs no access to the host.
* **FR2: Tracked training with hyperparameter search.** Each training run logs parameters, per-step metrics, system metrics, the dataset (with digest), seed, git commit and the model environment to the cluster MLflow. The search is an Optuna study with at least 5 nested trial runs under one parent run.
* **FR3: Configuration and secrets.** Parameters come from `params.yaml` / a ConfigMap; MLflow credentials come from a Kubernetes Secret or git-ignored files. No credentials in Git or in manifests.
* **FR4: Model registry.** Every trained model is registered as a new version of `sentiment-analyzer`. The alias `@champion` is the only source of the served model.
* **FR5: Training Job in the cluster.** A Kubernetes Job (Helm chart `infra/job-chart`) runs prepare -> train -> evaluate -> quality gate -> promote and ends `Completed` (gate passed) or `Failed` (gate blocked).
* **FR6: Inference API.** A FastAPI service in a Deployment + Service exposes `/health`, `/ping` and `/predict`, loading `models:/sentiment-analyzer@champion` from the registry at startup.
* **FR7: CI.** GitHub Actions runs lint and unit tests, then builds and pushes the inference and trainer images to GHCR tagged `sha-<commit>`.
* **FR8: Quality gate and rollback.** A model is promoted only if its evaluation metric reaches the threshold from `params.yaml` (`gate.min`). `@champion` can be moved back to the previous version and the pods restarted.

---

## 3. Non-Functional Requirements (NFR) & KPIs

Measured values come from the runs described in `docs/u2-report.md`.

| ID | Requirement | Target (KPI) | Measured | How measured |
|---|---|---|---|---|
| NFR1 | Reproducibility | Re-running the pipeline with the same code, parameters and seed gives eval-f1 within 0.005 of the original | True | `dvc repro` twice, compare `metrics/scores.json` |
| NFR2 | Inference latency | p95 of `/predict` < 150 ms | 8.84 ms | `scripts/loadtest.py`, 100 sequential requests -> `docs/loadtest.json` |
| NFR3 | Training resources | <= 2 CPU cores and <= 2 GB RAM at peak | 0.609 core(s), 225 MB | `kubectl top pod -n mlops-lab` sampled during the Job (peak values), compared with the Job limits (`cpu: 2`, `memory: 2Gi`) |
| NFR4 | Persistence | Run history and artifacts survive a restart of the MLflow pod | yes | delete the MLflow pod; the registry and an old artifact are still available |
| NFR5 | Security | 100 % of unauthenticated MLflow requests return 401 | True | `curl -s -o /dev/null -w "%{http_code}" http://localhost:5005/api/2.0/mlflow/experiments/search` |
| NFR6 | Throughput | >= 20 requests/s at 10 concurrent clients | 200 req/s | `scripts/loadtest.py` concurrent phase |
| NFR7 | Model size | <= 50 MB | 1.05KB | size of the model artifact in MLflow |
| NFR8 | Quality gate | A model with eval-f1 < `gate.min` is never promoted | - | red Job run: Job `Failed`, `@champion` unchanged |
| NFR9 | Rollback time | `@champion` rolled back and serving the old version in <= 2 min | 2.152 s | time from running the rollback command until `/health` shows the old `model_version` |

---

## 4. Out of scope
GPU training, LLM serving, a full Prometheus/Grafana stack, a new cluster (the U1 cluster is reused).
