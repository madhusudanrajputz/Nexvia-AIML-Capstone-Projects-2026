# AIML-01: Financial Fraud Detection Platform

## Overview

A financial fraud detection capstone developed for the Nexvia
Technologies AIML internship.

The platform combines PaySim transaction data, historical account
features, XGBoost classification, FastAPI inference, and an analyst
dashboard for fraud investigation.

## Technology

- Python, pandas, NumPy, XGBoost
- PyTorch Geometric and GraphSAGE experiments
- Feast feature store
- FastAPI
- Next.js and React
- SQLite
- Kafka streaming components
- Evidently monitoring
- MLflow experiment tracking
- Docker and Kubernetes demonstration configurations

## Architecture

```text
PaySim data
   |
   v
Historical feature engineering
   |
   +----> XGBoost training and evaluation
   |
   +----> GraphSAGE and ensemble experiments
   |
   v
Feast historical features
   |
   v
FastAPI + approved XGBoost model
   |
   v
Next.js fraud analyst dashboard
   |
   +----> Fraud prediction
   |
   +----> Automatic alert
               |
               v
          Analyst case API
               |
               v
          Analyst feedback
```

## Approved Model

The verified demonstration uses a 23-feature XGBoost baseline
with a decision threshold of 0.48456997.

Other XGBoost weighting and GraphSAGE experiments are included
as research and comparison work, not as the selected deployed model.

## Verified End-to-End Test

A historical PaySim fraud transaction, `paysim:5393914`,
was scored using a verified isolated Feast feature-store snapshot.

- Fraud probability: approximately 0.9998253
- Fraud alert: true
- Historical feature parity: 8/8
- Automatic analyst case: created and persisted in the local demo
- Authentication: unauthorized requests rejected

The verification report is stored at:

`results/metrics/Colab_Real_Fraud_End_to_End_Demo_Audit.json`

This is a fixed-hour development demonstration, not evidence
of a production continuous Kafka pipeline or full historical
account coverage.

## Project Components

- `api/`: fraud scoring and case-management services
- `dashboard/`: Next.js analyst dashboard
- `features/`: XGBoost serving feature contract
- `feast_repo/`: Feast registry and feature definitions
- `models/xgboost/`: approved model
- `deployment/render/`: Render deployment configuration
- `k8s/`: separate Kubernetes demonstration configuration
- `monitoring/`: monitoring experiments and outputs
- `results/metrics/`: model comparison and validation evidence
- `tests/`: available integration and component tests

## Deployment

### Verified Hosted Demonstration

Netlify dashboard:
https://aiml01-fraud-detection-demo.netlify.app/

The deployed Next.js demonstration uses the approved XGBoost
model and a frozen historical Feast feature snapshot.

Historical fraud scoring was tested successfully.
Public, unauthenticated evaluator accessibility must still
be confirmed before final submission.

### Other Deployment Configurations

- Render configuration and deployment instructions are included.
  A public Render deployment is not verified.
- Docker build definitions are included.
- Kubernetes and Minikube configuration is included.
  An actual cluster rollout is not verified.
- The original FastAPI, Kafka and Feast components remain
  separate from the hosted Netlify scoring implementation.

See ARCHITECTURE.md and API.md.

## Current Limitations

- Hosted scoring supports a fixed historical demonstration scope.
- Netlify does not run a continuous Kafka streaming pipeline.
- Persistent analyst-case storage is unavailable on Netlify.
- Local case-management integration has separate saved evidence.
- Production automatic retraining is disabled.
- The retraining trigger blocks unverified temporal sampling.
- Kubernetes cluster deployment is not runtime verified.
- GraphSAGE and ensemble experiments are not the hosted model.
- This prototype is not a production banking decision system.
