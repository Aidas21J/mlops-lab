# Project Requirements: Sentiment Analysis Pipeline
**Document Version:** v1.1  
**Project Domain:** Natural Language Processing (NLP) / Sentiment Analysis  
**Target Architecture:** MLflow, DVC (`localremote`), Terraform, Helm, Python Automation  

---

## 1. Problem Statement
The goal of this system is to automatically classify movie reviews (positive/negative) using a reproducible machine learning pipeline.
The project must ensure version-controlled local data artifacts, automated script-driven hyperparameter sweeps, experiment tracking, and strict auditability of experiment metrics.

---

## 2. Functional Requirements (FR)

* **FR1: Data Version Control & Ingestion**
  * The system must use DVC coupled with a local directory storage backend (`localremote`) to track and version dataset snapshots.
  The training pipeline must automatically pull the correct dataset version via `dvc repro --pull` before execution.
* **FR2: Automated Hyperparameter Training & Experiment Logging**
  * The system must execute automated training sweeps (varying hyperparameters such as regularization parameter $C$ and `max_features`)
  via an automation script (`run-sweep.sh`) and log all parameters, metrics, and model artifacts to a centralized MLflow server protected by basic authentication.
* **FR3: Script-Driven Pipeline & Environment Configuration**
  * The system must provide a streamlined script-driven workflow that dynamically injects secure environment configurations
  (such as MLflow tracking URIs and credentials) from local variable files without exposing plaintext secrets in source control or terminal histories.

---

## 3. Non-Functional Requirements (NFR) & KPIs

* **NFR1: Experiment Reproduction (Reproduction NFR)**
  * **Description:** The training pipeline must be fully deterministic and reproducible given the same code state and parameter configuration. 
  * **KPI:** Reproduced evaluation metrics (`eval-accuracy`, `eval-f1`) must match the original logged run within an absolute tolerance delta of $\le 0.005$.
* **NFR2: Inference Latency (Performance)**
  * **Description:** The deployed model inference service must return text classification predictions rapidly to support client applications.
  * **KPI:** 95th percentile (P95) response time for inference requests must be $< 150\text{ms}$.
* **NFR3: Resource Constraints (Scalability / Efficiency)**
  * **Description:** Training execution processes must run within constrained resource limits to allow local evaluation without crashing the host environment.
  * **KPI:** Individual training runs must consume $\le 2.0$ CPU cores and $\le 2.0\text{GB}$ of RAM during peak execution.
* **NFR4: System Reliability & Availability**
  * **Description:** The MLflow tracking server and backend database must ensure persistent state storage across service restarts or platform reboots.
  * **KPI:** Database and artifact storage availability must be $\ge 99.9\%$, with zero loss of historical run metadata across restarts.
* **NFR5: Platform Security & Access Control**
  * **Description:** Access to experiment tracking, model registries, and administrative features must be strictly protected via authentication.
  * **KPI:** 100% of unauthenticated API or UI requests to the MLflow tracking server must be blocked with a `401 Unauthorized` response code.
