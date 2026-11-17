# AIML-03: Personalized Movie Recommendation Engine

**Organization: Nexvia Technologies**

## Overview

A MovieLens 25M-based personalized movie recommendation
system featuring neural retrieval, FAISS indexing,
Wide & Deep ranking, API serving and evaluation.

## Main Components

- MovieLens 25M preprocessing
- Chronological train/validation/test split
- Two-Tower retrieval model
- FAISS candidate retrieval
- Wide & Deep ranking
- Popularity baseline
- Cold-start recommendation support
- FastAPI and Redis integration
- Gradio user interface
- ONNX ranking inference
- Apache Airflow workflows

## Evaluation

The project includes Recall@10, NDCG@10,
per-user evaluation and bootstrap confidence intervals.

The preliminary paired offline evaluation favors the
Popularity Baseline over the Two-Stage recommender.

The results are limited to a selected evaluation sample,
and remaining evaluation limitations are documented.

## A/B Testing

A reproducible synthetic A/B testing demonstration
includes:

- Deterministic user assignment
- Synthetic impression and click events
- CTR calculation
- User-level bootstrap confidence intervals

The synthetic CTR results are not evidence of
real-world click-through rates or causal uplift.

See:
results/ab_testing/AB_V2_Final_Experiment_Report.md

## Airflow Automation

Verified workflows:

1. Daily scheduled artifact and evaluation validation
2. Weekly scheduled retrieval smoke retraining
3. FAISS staging index rebuilding
4. Staging artifact validation

Production promotion is disabled.

Airflow was tested in a temporary Google Colab runtime.
Continuous unattended hosting is not established.

Evidence:
results/airflow_validation/

## Deployment

Implemented components include:

- FastAPI
- Redis integration
- Gradio dashboard
- ONNX model export and CPU inference

NVIDIA Triton Inference Server 2.74.0 successfully served the ranking ONNX model through HTTP on CPU. The prediction matched direct ONNX Runtime inference exactly for the tested input.

## Documentation

Reports and presentation files are available
in the reports/ directory.

## Important Limitations

- Real online A/B testing has not been performed.
- Synthetic clicks are not real user interactions.
- Offline model performance needs further improvement.
- Full scheduled model retraining is not verified.
- Production-scale Triton load testing and GPU serving have not been verified.
- Production deployment is not established.

## Project Status

Core recommendation pipeline and offline evaluation
are implemented.

Scheduled smoke retraining and validation have
been successfully demonstrated.

Spark preprocessing regeneration passed for all five feature datasets. Triton HTTP inference and local Redis caching were verified.

Remaining work includes final submission verification, demonstration recording and production deployment validation.
