
import os
import sys
from pathlib import Path

import pendulum
from airflow.sdk import dag, task


@dag(
    dag_id="aiml03_daily_artifact_validation",
    description="Daily validation of AIML-03 artifacts and evaluation",
    start_date=pendulum.datetime(
        2026, 10, 23, tz="Asia/Kolkata"
    ),
    schedule="0 9 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["AIML-03", "scheduled", "validation"]
)
def daily_artifact_validation():

    @task
    def validate_artifacts_task():

        project = Path(os.environ["AIML03_PROJECT_DIR"])
        sys.path.insert(0, str(project / "airflow"))

        from validate_artifacts import validate_artifacts

        result = validate_artifacts(project)

        if result["status"] != "PASS":
            raise ValueError(
                f"Artifact validation failed: {result}"
            )

        print("Daily artifact validation:", result)
        return result

    @task
    def validate_evaluation_task(artifact_result):

        if artifact_result["status"] != "PASS":
            raise ValueError("Previous validation failed")

        project = Path(os.environ["AIML03_PROJECT_DIR"])
        sys.path.insert(0, str(project / "airflow"))

        from validate_evaluation import validate_evaluation

        result = validate_evaluation(project)

        if result["status"] != "PASS":
            raise ValueError(
                f"Evaluation validation failed: {result}"
            )

        print("Daily evaluation validation:", result)
        return result

    artifacts = validate_artifacts_task()
    validate_evaluation_task(artifacts)


daily_artifact_validation()
