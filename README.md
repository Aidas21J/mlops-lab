# Sentiment Analysis MLOps Pipeline

A reproducible, automated MLOps pipeline for classifying text sentiment using **Terraform**, **Helm**, **Kubernetes (Kind)**, **MLflow**, **DVC**, and **Python**.

This repository provisions a local Kubernetes cluster hosting a production-grade MLflow tracking infrastructure (backed by PostgreSQL for metadata and a Persistent Volume for artifacts) and provides a script-driven workflow for hyperparameter optimization and model versioning.

---

## System Architecture

```text
                                +----------------------------------------+
                                |               Local Host               |
                                |                                        |
                                |  +----------------------------------+  |
                                |  | dvc repro OR run-sweep.sh script |  |
                                |  +----------------+-----------------+  |
                                |                   |                    |
                                |                   v                    |
                                |     +-----------------------------+    |
                                |     |       DVC (localremote)     |    |
                                |     +-----------------------------+    |
                                +-------------------+--------------------+
                                                    |
                                                    v  (Port 5005)
+-----------------------------------------------------------------------------------+
| Kind Kubernetes Cluster ('mlops-cluster')                                         |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | Namespace: mlops-lab                                                      |   |
|   |                                                                           |   |
|   |   +-----------------------+              +----------------------------+   |   |
|   |   |    MLflow Service     | ------------>|     PostgreSQL Database    |   |   |
|   |   |   (NodePort 30000)    |  (App DB)    |     (Persistent Storage)   |   |   |
|   |   +-----------+-----------+              +----------------------------+   |   |
|   |               |                                                           |   |
|   |               v (Artifact Storage)                                        |   |
|   |   +-------------------------------------------------------------------+   |   |
|   |   |              Persistent Volume Claim (mlflow-artifacts-pvc)       |   |   |
|   |   +-------------------------------------------------------------------+   |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

---

## Prerequisites

Ensure you have the following installed on your system:

* [Docker Desktop](https://www.docker.com/) (running)
* [Terraform](https://developer.hashicorp.com/terraform/downloads) ($\ge 1.0$)
* [Python 3.10+](https://www.python.org/)

---

## Quick Start Guide

### 1. Repository Setup & Dependencies

After cloning the repository (and going into the repo's root directory) set up your local Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Infrastructure Variables

Create your local `infra/terraform.tfvars` file (this file is ignored by Git to keep credentials secure):

*Note:* `mlflow_admin_password` is enforced be at least 12 characters long.

```hcl
mlflow_admin_password = "SuperAdminPassword123!"
flask_secret_key      = "a-very-secret-flask-key"

# Host port mappings
mlflow_host_port      = 5005
inference_host_port   = 8008
```

### 3. Provision Infrastructure via Terraform

Initialize and apply the Terraform configuration to build the Kind Kubernetes cluster and deploy the MLflow stack via Helm:

```bash
cd infra
terraform init
terraform apply -auto-approve
cd ..
```

* **MLflow UI:** Accessible at `http://localhost:5005`
* **Username:** `admin`
* **Password:** *(the value set in `infra/terraform.tfvars`)*

*Note:* To use commands like `dvc repro` set following variables (values must match `infra/terraform.tfvars` info):
```bash
export MLFLOW_TRACKING_URI="<MLflow UI URI>"
export MLFLOW_TRACKING_USERNAME="<Username>"
export MLFLOW_TRACKING_PASSWORD="<Password>"
```

---

## Running Hyperparameter Sweeps & Training

Since training runs are stored in a cluster there isn't a trivial way to share runs.
To run automated training iterations with different hyperparameters and log metrics, parameters, and model artifacts directly into MLflow, execute the master sweep script:

```bash
chmod +x scripts/three-runs.sh
./scripts/three-runs.sh
```

### What `three-runs.sh` does automatically:
1. Dynamically reads `mlflow_host_port` and `mlflow_admin_password` from `infra/terraform.tfvars`.
2. Activates the Python virtual environment (`.venv`).
3. Loops through specified values of parameter $C$ (`0.5`, `1.0`, `2.0`), updating `params.yaml` safely.
4. Runs `dvc repro` for each iteration.
5. Logs $3$ distinct runs with metrics (`eval-accuracy`, `eval-f1`) and model artifacts to the MLflow server.

---

## Data Version Control (DVC)

This project uses DVC with a `localremote` storage directory to track raw and processed dataset artifacts.

* **Pull latest data version:**
  ```bash
  dvc pull
  ```
* **Reproduction pipeline:**
  ```bash
  dvc repro
  ```

---

## Project Structure

```text
.
├── docs/
│   └── requirements.md         # Software and pipeline requirements (v1.1)
├── infra/
│   ├── main.tf                 # Terraform config (Kind cluster & Helm release)
│   ├── terraform.tfvars        # Local credentials and ports (Git-ignored)
│   └── mlops-lab-chart/        # Helm chart for MLflow and PostgreSQL
├── scripts/
│   ├── bootstrap.py            # Pull datasets from Hugging Face
│   ├── reproduce.py            # Reproduces run from its run_id (`python scripts/reproduce.py <run_id>)
│   └── three-runs.sh           # Runs the three training runs
├── src/
│   ├── prepare.py              # Prepare raw data for training
│   ├── train.py                # Model training script with MLflow logging
│   └── evaluate.py             # Evaluation metrics generation
├── data/                       # Tracked via DVC
├── dvc.yaml                    # DVC pipeline pipeline configuration
├── params.yaml                 # Model hyperparameters
├── requirements-inference.txt  # Python dependencies for inference only
└── requirements.txt            # Python dependencies
```

---

## Cleanup

To tear down the cluster and clean up all local Kubernetes resources:

```bash
cd infra
terraform destroy -auto-approve
```
