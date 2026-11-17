FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/api:/app/scripts

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1" \
    "uvicorn>=0.30,<1" \
    "pydantic>=2,<3" \
    "numpy>=1.26,<3" \
    "pandas>=2,<3" \
    "xgboost==3.4.1" \
    "feast==0.68.0"

COPY api/ /app/api/
COPY scripts/fraud_serving_features.py /app/scripts/
COPY features/XGBoost_Feature_Contract.json /app/features/
COPY models/xgboost/XGBoost_Unweighted_Baseline.json /app/models/xgboost/
COPY feast_repo/ /app/feast_repo/

WORKDIR /app/api

CMD ["uvicorn", "fraud_api_deployment:app", "--host", "0.0.0.0", "--port", "8000"]
