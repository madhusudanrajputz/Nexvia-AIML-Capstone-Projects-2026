# AIML-01 System Architecture

## 1. Overview

The project combines historical transaction modeling,
feature engineering, fraud scoring, streaming infrastructure
experiments, monitoring, and analyst investigation components.

## 2. Model Development

PaySim transactions
    |
    v
Preprocessing and historical account feature engineering
    |
    +--> XGBoost classification and evaluation
    |
    +--> GraphSAGE / fraud-ring experiments
    |
    v
Model comparison and evaluation evidence
    |
    v
Approved 23-feature XGBoost model

The approved model is the hosted scoring model.
The GNN and ensemble experiments are not deployed on Netlify.

## 3. Hosted Demonstration

Historical PaySim transaction
    |
    v
Frozen historical account feature snapshot
    |
    v
23-feature serving contract
    |
    v
Approved XGBoost decision model
    |
    v
Next.js prediction API
    |
    v
Fraud scoring dashboard

The classification threshold is 0.48456997.

The hosted snapshot has limited account and temporal coverage.
It must not be presented as a continuously updating Feast store.

## 4. Separate Development Components

- Kafka transaction replay and consumption
- Feast feature storage and account-history engineering
- FastAPI fraud scoring
- SQLite-backed streaming state and analyst-case services
- Durable dead-letter and recovery mechanisms
- Evidently drift analysis and alert policy
- MLflow experiment tracking
- Retraining trigger, approval coordinator, and challenger worker
- Docker and Kubernetes demonstration configurations

These components have different verification scopes.
Their presence in the repository does not establish that
they are all running together in production.

## 5. Monitoring and Retraining

Evidently drift evaluation
    |
    v
Drift alert policy
    |
    v
Retraining trigger safety checks
    |
    +--> BLOCKED when temporal sampling is unverified
    |
    +--> Eligible request only after verification

Human approval is required for further retraining actions.
Automatic production retraining and model promotion are disabled.

## 6. Deployment Status

- Netlify historical scoring: tested
- Local end-to-end historical fraud case: tested
- Continuous production Kafka scoring: not verified
- Production retraining automation: not verified
- Kubernetes cluster rollout: not verified

## 7. Evidence

See results/metrics/ for saved model, integration and
deployment-related audits.

See monitoring/ for drift reports and policy configuration.

See k8s/ for Kubernetes demonstration manifests and scripts.
