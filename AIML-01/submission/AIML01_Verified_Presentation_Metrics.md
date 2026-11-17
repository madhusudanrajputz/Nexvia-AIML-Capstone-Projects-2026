# AIML-01 Verified Presentation Metrics

## Approved Model

- Model: XGBoost Unweighted Baseline
- Features: 23
- Validation Average Precision (PR-AUC): 0.962893
- Validation precision at selected threshold: 0.842809
- Validation recall at selected threshold: 0.900000
- Validation F1 at selected threshold: 0.870466
- Selected threshold: 0.48456997
- Validation missed frauds: 56

## Model Comparison

| Model | Validation Average Precision | Selection |
| --- | ---: | --- |
| XGBoost baseline | 0.962893 | Approved |
| Weighted XGBoost | 0.958576 | Not selected |
| XGBoost 31 features | 0.954520 | Not selected |
| GraphSAGE full validation | 0.020852 | Not selected |

The GraphSAGE sampled validation Average Precision was
0.747301,
but the sampled validation prevalence was
10.0%.

The full validation fraud prevalence was
0.0594%.
The full validation result must be used for fair comparison
with the approved XGBoost model.

The selected ensemble GNN weight was
0.0.
The approved hosted model was not replaced.

## Verified Historical Fraud Demonstration

- Transaction: paysim:5393914
- Fraud probability: 0.999825299
- Classification threshold: 0.48456997
- Fraud alert: True
- Local case creation: CREATED
- Local case status: OPEN
- Case API HTTP response: 200
- Unauthorized request HTTP response: 401

## Scope and Limitations

These are saved validation and historical development-demo
results, not production financial-system metrics.

The hosted Netlify demonstration performs historical scoring
with a frozen feature snapshot. The local analyst-case result
does not imply persistent case storage on Netlify.

Continuous hosted Kafka streaming, Kubernetes cluster rollout,
and automatic production retraining are not verified.

## Source Reports

- results/metrics/XGBoost_Unweighted_Baseline.json
- results/metrics/XGBoost_Weighted_SqrtRatio.json
- results/metrics/XGBoost_Velocity_31Features.json
- results/metrics/XGBoost_Validation_Threshold_Decision.json
- results/metrics/XGBoost_GraphSAGE_Ensemble_Decision.json
- results/metrics/GraphSAGE_Validation_Metrics.json
- results/metrics/GraphSAGE_Full_Validation_Metrics.json
- results/metrics/Colab_Real_Fraud_End_to_End_Demo_Audit.json
