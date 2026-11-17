# AIML-01 Individual Reflection (Draft for Personal Review)

## Project Overview

This capstone involved developing and evaluating components of a
financial fraud detection platform using PaySim transaction data.

## Technical Learning

The project provided practical experience with transaction feature
engineering, imbalanced classification, XGBoost, graph-based fraud
experiments, Feast, Kafka, FastAPI, model monitoring, and deployment.

## Engineering Challenges

Important engineering challenges included preserving historical
feature consistency, recovering streaming state after interruptions,
checking prediction parity, and preventing unverified monitoring
signals from automatically initiating retraining.

## Results and Limitations

A historical fraud transaction was successfully scored using the
approved XGBoost model. Separate integration audits provide evidence
for several Kafka, Feast, and API components.

The hosted Netlify demo uses a frozen historical feature snapshot.
Continuous production streaming, Kubernetes cluster rollout, and
automatic production retraining are not verified.

## Personal Contribution and Growth

During this project, I worked on developing and evaluating
a financial fraud detection prototype. My work involved
investigating transaction features, comparing machine learning
models, examining model performance, and integrating components
needed for fraud prediction and analyst review.

I also worked through practical integration challenges
involving feature consistency, API testing, streaming-state
recovery, and deployment. These activities helped me understand
the difference between developing an ML model and delivering
a reliable end-to-end application.

An important decision was to retain the validated XGBoost
baseline rather than claim an improvement from the GraphSAGE
experiment. I learned that model selection should depend on
representative evaluation results rather than a single
promising experiment.

The project improved my understanding of reproducible machine
learning, integration testing, model monitoring, and honest
reporting of system limitations.



## Future Improvements

Future work could include verifying Kubernetes deployment,
continuous hosted streaming, independent temporal monitoring
validation, and safe model retraining with controlled promotion.
