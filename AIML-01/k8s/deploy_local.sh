#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "AIML-01: Local Kubernetes Demo Deployment"

for command in docker minikube kubectl openssl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Missing required command: $command"
        exit 1
    fi
done

if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon unavailable."
    exit 1
fi

if ! minikube status >/dev/null 2>&1; then
    echo "Start Minikube first:"
    echo "  minikube start --driver=docker"
    exit 1
fi

kubectl config use-context minikube >/dev/null

echo "Building backend image..."
minikube image build \
    -t aiml01-backend:demo \
    -f docker/backend.Dockerfile .

echo "Building dashboard image..."
minikube image build \
    -t aiml01-dashboard:demo \
    -f docker/dashboard.Dockerfile .

echo "Generating demo-only Kubernetes secrets..."

BACKEND_KEY="$(openssl rand -hex 32)"
CASES_KEY="$(openssl rand -hex 32)"
ACCESS_CODE="$(openssl rand -hex 16)"

SECRET_FILE="$(mktemp)"
chmod 600 "$SECRET_FILE"

cleanup() {
    rm -f "$SECRET_FILE"
}
trap cleanup EXIT

{
    printf 'backend-api-key=%s\n' "$BACKEND_KEY"
    printf 'cases-api-key=%s\n' "$CASES_KEY"
    printf 'dashboard-access-code=%s\n' "$ACCESS_CODE"
} > "$SECRET_FILE"

kubectl create secret generic aiml01-demo-secrets \
    --from-env-file="$SECRET_FILE" \
    --dry-run=client \
    -o yaml | kubectl apply -f - >/dev/null

unset BACKEND_KEY CASES_KEY

echo "Applying Kubernetes deployment..."
kubectl apply -f k8s/aiml01-demo.yaml

echo "Checking deployment rollout..."
if ! kubectl rollout status \
    deployment/aiml01-demo --timeout=300s; then
    echo "Deployment has not become ready."
    kubectl get pods -l app=aiml01-demo
    exit 1
fi

echo
echo "Deployment rollout completed."
echo "Dashboard access code: $ACCESS_CODE"
echo
echo "Start local dashboard access with:"
echo "kubectl port-forward --address 127.0.0.1 service/aiml01-dashboard 3000:3000"
echo
echo "Then open: http://127.0.0.1:3000"
echo
echo "Check Pod state:"
echo "kubectl get pods -l app=aiml01-demo"
echo
echo "This is a fixed-hour development demo."
echo "Rollout readiness does not prove prediction correctness."
