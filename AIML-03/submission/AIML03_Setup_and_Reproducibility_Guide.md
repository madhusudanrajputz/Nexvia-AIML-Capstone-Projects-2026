# AIML-03 Setup and Reproducibility Guide

**Organization: Nexvia Technologies**

## 1. Project Overview

Movie recommendation prototype using MovieLens 25M,
Two-Tower retrieval, FAISS indexing, Wide & Deep ranking,
FastAPI, Redis, Gradio and Apache Airflow.

## 2. Submission Packages

- AIML03_Final_Verified_2026-11-04_v2.zip:
  Updated report, presentation and verified execution evidence.

- AIML03_Source_Verified_2026-11-04_v2.zip:
  Selected training, preprocessing, deployment and Airflow source.

- AIML03_Master_Verified_2026-11-04_v2.zip:
  Contains the two versioned ZIP packages above.

These packages do not contain the full dataset,
trained weights, FAISS indexes or all generated artifacts.

## 3. Python Environment

Validated Google Colab runtime:

- Python: 3.13.18
- TensorFlow: 2.21.0
- TensorFlow Recommenders: 0.7.7
- TF-Keras: 2.21.0
- Keras: 3.13.2
- FAISS CPU: 1.15.1
- NumPy: 2.4.6

The deployment requirements file specifies NumPy 2.1.3,
which differs from the tested training runtime.

Dependency compatibility on a fresh machine has
not been independently verified.

## 4. Additional Training Dependencies

The retrieval training script requires:

- tensorflow-recommenders==0.7.7

The FAISS rebuild script requires:

- faiss-cpu==1.15.1
- tf-keras==2.21.0

The tested training subprocess used:

TF_USE_LEGACY_KERAS=1
CUDA_VISIBLE_DEVICES=-1

## 5. Configuration

Before running Airflow on a new machine, copy:

`airflow/training_runner_config.example.json`

to:

`airflow/training_runner_config.json`

Then replace placeholder paths with the actual paths for that machine. The private Colab runtime configuration is not included in the source package.

Important fields:

- project_dir: absolute location of the extracted project
- training_python: Python interpreter with ML dependencies
- training_script: absolute path to training/train_retrieval.py

Keep:

- mode: smoke
- epochs: 1
- promotion_enabled: false

Other scripts may require additional environment-specific
paths or configuration.

## 6. Data and Model Artifacts

The source archive alone is not sufficient for execution.

The application requires appropriate saved model files,
FAISS indexes, processed data snapshots and supporting
artifacts from the original project.

MovieLens 25M must be obtained according to its dataset terms.

## 7. Airflow Evidence

Verified in temporary Google Colab:

- Daily scheduled validation: PASS
- Weekly scheduled one-epoch retrieval training: PASS
- FAISS staging rebuild: PASS
- Staging validation: PASS

Continuous unattended hosting has not been verified.

## 8. Evaluation Limitations

The preliminary offline comparison used 55 selected users.

Popularity Baseline outperformed the Two-Stage model
on the reported Recall@10 and NDCG@10 metrics.

The A/B demonstration uses synthetic impressions and clicks.
It is not a real online randomized experiment.

## 9. Triton Status

ONNX Runtime CPU inference: VERIFIED.

NVIDIA Triton HTTP inference: VERIFIED on CPU using the ONNX Runtime backend.

A live NVIDIA Triton 2.74.0 HTTP request returned status 200 and the same ranking prediction as direct ONNX Runtime inference. Production deployment and load testing remain unverified.

## 10. Reproducibility Status

Source files: PACKAGED
Execution evidence: PACKAGED
Five Spark preprocessing feature datasets: REPRODUCED AND VERIFIED
Fresh environment end-to-end model training and deployment: NOT VERIFIED
Production deployment: NOT VERIFIED

## 11. Spark Feature Reproduction

Source: `preprocessing/build_spark_features.py`

Input: `data/raw/ml-25m.zip`

Verified cutoff candidate: `1466837397`

The source script accepts `--archive`, `--output`,
`--workdir` and `--cutoff` arguments. Use a new output
directory; the script refuses to overwrite an existing
output directory.

The independent regeneration produced five Parquet
datasets with matching schemas, row counts and values.

Evidence: `results/spark_validation/Spark_Reproducibility_Evidence.json`

## 12. Triton and Redis Validation

Triton HTTP endpoint used for local verification:
`http://127.0.0.1:8005/v2/models/ranking/infer`

Ranking model version: 1

Backend: ONNX Runtime, CPU

Triton inference matched direct ONNX Runtime inference
with maximum absolute difference of 0.0 for the tested input.

Evidence:
`results/triton_validation/Triton_Live_HTTP_Inference_Evidence.json`

Redis-backed FastAPI recommendations were locally tested
with cache MISS and HIT behavior. The local Colab services
are not equivalent to a permanently hosted deployment.

## 13. Remaining Reproducibility Limitations

The submission packages do not include the full dataset,
trained model weights or all generated artifacts.

Complete fresh-environment model retraining, production
deployment, unattended continuous Airflow operation and
real online A/B testing have not been verified.
