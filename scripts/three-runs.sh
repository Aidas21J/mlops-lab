#!/bin/bash
set -e

TFVARS_FILE="infra/terraform.tfvars"

# Dynamically extract the MLflow host port from terraform.tfvars (fallback to 5005 if not specified)
if [ -f "$TFVARS_FILE" ]; then
    MLFLOW_PORT=$(grep -E '^\s*mlflow_host_port\s*=' "$TFVARS_FILE" | cut -d'=' -f2 | tr -d '[:space:]')
    MLFLOW_PORT=${MLFLOW_PORT:-5005} # Default to 5005
    
    # 2. Dynamically extract the MLflow admin password
    MLFLOW_PASS=$(grep -E '^\s*mlflow_admin_password\s*=' "$TFVARS_FILE" | cut -d'"' -f2)
else
    MLFLOW_PORT=5005
    echo "infra/terraform.tfvars not found. Type your MLflow admin password:"
    read -rs MLFLOW_PASS
fi

export MLFLOW_TRACKING_URI="http://localhost:${MLFLOW_PORT}"
export MLFLOW_TRACKING_USERNAME="admin"
export MLFLOW_TRACKING_PASSWORD="${MLFLOW_PASS}"

echo "🔗 Target MLflow Tracking URI set to: $MLFLOW_TRACKING_URI"

C_VALUES=(0.5 1.0 2.0)

for c_val in "${C_VALUES[@]}"; do
    echo "=================================================="
    echo "Starting DVC pipeline run with C = $c_val"
    echo "=================================================="

    python3 -c "
import yaml
with open('params.yaml', 'r') as f:
    params = yaml.safe_load(f)
params['train']['C'] = float($c_val)
with open('params.yaml', 'w') as f:
    yaml.safe_dump(params, f, sort_keys=False)
"

    dvc repro

    echo "Finished run for C = $c_val"
    echo ""
done

echo "All 3 hyperparameter training runs completed successfully!"
