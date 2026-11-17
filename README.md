# Nexvia Technologies | AI/ML Internship Capstone Projects

**Intern:** Madhusudan Kumar Singh  
**Internship:** 20 October - 20 November 2026  
**Specialization:** Artificial Intelligence / Machine Learning

This repository contains the two assigned internship capstone projects,
their selected source code, model artifacts, evaluation evidence,
technical documentation, and presentation materials.

## Projects

| ID | Project | Implementation |
| --- | --- | --- |
| AIML-01 | Real-Time Financial Fraud Detection Platform | PaySim, XGBoost, GraphSAGE, Kafka, Feast, MLflow, FastAPI, Evidently, Next.js |
| AIML-03 | Personalized Movie Recommendation Engine | MovieLens 25M, Two-Tower, FAISS, Wide & Deep, FastAPI, Redis, Gradio, Airflow |

## AIML-01: Fraud Detection

[Project source and documentation](AIML-01/)

**Deployed demonstration:**  
https://aiml01-fraud-detection-demo.netlify.app/

The hosted Next.js application performs authenticated fraud scoring
using the approved 23-feature XGBoost model and a frozen historical
Feast feature snapshot.

The approved classification threshold is **0.48456997**.

A verified historical PaySim fraud transaction, `paysim:5393914`,
produced approximately **0.9998253 fraud probability**.

The hosted demonstration is restricted to supported historical
transactions. It is not a continuously operating banking service.

### AIML-01 Architecture

PaySim transactions
-> historical account feature engineering
-> XGBoost training and GraphSAGE experiments
-> Feast feature representation
-> authenticated fraud scoring
-> analyst-facing Next.js dashboard

Kafka streaming, FastAPI services, local analyst-case persistence,
monitoring, and Kubernetes demonstration configurations are included
as separate development components.

### AIML-01 Limitations

- Netlify uses a frozen historical Feast snapshot.
- Continuous Kafka streaming is not deployed on Netlify.
- Persistent investigation-case management is unavailable on Netlify.
- Production automatic retraining is not enabled.
- The retraining trigger blocks unverified temporal sampling.
- Kubernetes manifests exist, but cluster rollout remains unverified.
- GraphSAGE and ensemble experiments are not the approved hosted model.

## AIML-03: Movie Recommendation

[Project source and documentation](AIML-03/)

The MovieLens 25M recommendation prototype includes:

1. Data preprocessing and chronological evaluation.
2. Two-Tower candidate retrieval.
3. FAISS nearest-neighbor candidate search.
4. Wide & Deep ranking.
5. Popularity and content-based fallback recommendations.
6. FastAPI serving and optional Redis caching.
7. Gradio interface and Airflow validation workflows.

### AIML-03 Architecture

MovieLens 25M
-> feature preprocessing
-> Two-Tower retrieval
-> FAISS candidates
-> Wide & Deep ranking
-> FastAPI recommendations
-> Gradio user interface

### AIML-03 Evaluation and Limitations

The selected offline evaluation sample favored the popularity
baseline over the current two-stage neural recommender.

The A/B experiment uses synthetic impressions and clicks;
it does not establish real production click-through uplift.

Spark feature reproduction, local API tests, Redis caching,
Airflow smoke workflows, and Triton CPU inference have
supporting saved evidence.

Permanent production deployment, continuous unattended Airflow
operation, and full fresh-environment retraining are not verified.

## Repository Layout

```text
AIML-01/
    api/
    dashboard/
    scripts/
    models/
    graph/
    feast_repo/
    monitoring/
    k8s/
    results/

AIML-03/
    preprocessing/
    training/
    deployment/
    airflow/
    models/
    faiss_index/
    reports/
    results/
    submission/
```

## Documentation and Evidence

- [AIML-01 README](AIML-01/README.md)
- [AIML-01 evaluation and audit evidence](AIML-01/results/metrics/)
- [AIML-01 monitoring evidence](AIML-01/monitoring/)
- [AIML-03 README](AIML-03/README.md)
- [AIML-03 setup guide](AIML-03/submission/AIML03_Setup_and_Reproducibility_Guide.md)
- [AIML-03 report and presentation](AIML-03/reports/)
- [AIML-03 evaluation evidence](AIML-03/results/)

## Setup and Reproducibility

Each project has separate dependencies and runtime requirements.
Follow the project-specific README and deployment instructions.

Do not assume the original Python services run inside the Netlify
serverless deployment. The AIML-01 Netlify demonstration uses
its own Next.js scoring endpoints.

The AIML-03 repository includes selected model weights, FAISS
indexes, source code, and deployment snapshots. The full
MovieLens 25M dataset is not bundled.

Some workflows require infrastructure and environment-specific
configuration. Saved evidence does not imply that all distributed
services are permanently hosted.

## Security

No credentials are intentionally included.
Configure passwords, API keys, and access codes using environment
variables or local secret stores.

## Academic and Engineering Scope

These are internship research and engineering prototypes.
Reported evaluations and tested components are distinguished
from features not yet verified in production.
