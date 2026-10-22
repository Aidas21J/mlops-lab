# U1 Assignment Report: MLOps Pipelines & Infrastructure

## 1. What Was Accomplished

* **Infrastructure as Code (IaC) & Local Cluster Provisioning:**
  * Modular Terraform configuration (`infra/main.tf`) that automates local **Kind (Kubernetes in Docker)** cluster creation and **Helm** release deployments.
  * Custom Helm chart (`mlops-lab-chart`) provisioning a PostgreSQL metadata database, an MLflow tracking server with a dedicated Persistent Volume Claim (`mlflow-artifacts-pvc`), and container health probes.
  * Implemented dynamic secret and parameter injection via local, git-ignored `terraform.tfvars`, ensuring zero plaintext credentials in source control.

* **Data Version Control & Experiment Tracking:**
  * Configured **DVC** with a local directory backend (`localremote`) to version raw and processed snapshots of the Rotten Tomatoes movie review dataset.
  * Integrated Python training scripts with the MLflow REST API to dynamically record hyperparameter configurations (`C`, `max_features`), metrics (`accuracy`, `f1`), and serialized scikit-learn model artifacts.

* **Automated Experiment Sweeps:**
  * Developed a master bash execution script (`scripts/three-runs.sh`) that reads port mappings and admin credentials directly from `terraform.tfvars`,
  detects active Python virtual environments, and runs **3 hyperparameter sweep iterations** by safely modifying `params.yaml` and executing `dvc repro`.

---

## 2. Technical Challenges & Solutions (What Didn't Work Initially)

1. **GCP Cloud Storage & Enterprise IAM Restrictions:**
   * *Issue:* Initially attempted to use Google Cloud Storage (GCS) as a remote DVC backend managed by Terraform. An organization policy (`iam.disableServiceAccountKeyCreation`) blocked service account JSON key generation.
   * *Solution:* Switched to a self-contained local DVC remote (`localremote`), eliminating cloud credential dependencies while maintaining 100% data versioning reproducibility for reviewers.

2. **Persistent Storage & Database Lifecycle Across Destroys:**
   * *Issue:* Running `terraform destroy` wiped the Kind cluster and internal database volumes, resetting experiment history.
   * *Solution:* Decoupled training execution from static cluster resources and designed `scripts/three-runs.sh` to automatically regenerate 3 fresh, valid runs in MLflow whenever a new cluster is provisioned.

---

## 3. Time Breakdown

**Total Time Spent:** ~31 Hours

* **Infrastructure Automation (Terraform, Kind, Helm):** ~15 hours
* **DVC & MLflow Integration (Python & Pipelines):** ~10 hours
* **Troubleshooting Cloud Remotes & Secret Handling:** ~5 hours
* **Script Automation & Documentation (`scripts/three-runs.sh`, `README.md`, `requirements.md`):** 1 hour
