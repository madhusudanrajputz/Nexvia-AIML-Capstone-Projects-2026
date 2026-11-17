
import os
import json
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pendulum
from airflow.sdk import dag, task, get_current_context


@dag(
    dag_id="aiml03_ranking_retraining_smoke",
    start_date=pendulum.datetime(
        2026, 10, 22, tz="Asia/Kolkata"
    ),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["AIML-03", "ranking", "training"]
)
def ranking_retraining_smoke():

    @task
    def validate_training_inputs():

        project = Path(os.environ["AIML03_PROJECT_DIR"])

        required = [
            project / "training" / "train_ranking.py",
            project / "data/processed/ranking_internal_train.parquet",
            project / "data/processed/ranking_internal_validation.parquet"
        ]

        for path in required:
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(path)

        print("Ranking input files verified!")

        return str(project)

    @task
    def train_ranking(project_path):

        project = Path(project_path)

        config = json.loads(
            (
                project / "airflow"
                / "training_runner_config.json"
            ).read_text(encoding="utf-8")
        )

        if config["mode"] != "smoke":
            raise ValueError("Smoke mode required")

        if config["promotion_enabled"] is not False:
            raise ValueError("Promotion must remain disabled")

        context = get_current_context()
        run_id = context["run_id"]

        run_hash = hashlib.sha256(
            run_id.encode("utf-8")
        ).hexdigest()[:16]

        output_name = "ranking_retrain_" + run_hash
        output_dir = project / "staging" / output_name

        if output_dir.exists():
            raise FileExistsError(output_dir)

        command = [
            config["training_python"],
            str(project / "training" / "train_ranking.py"),
            "--project-dir", str(project),
            "--output-name", output_name,
            "--epochs", "1",
            "--smoke"
        ]

        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "-1"
        env["TF_CPP_MIN_LOG_LEVEL"] = "2"

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Ranking training failed:\n"
                + result.stdout[-2000:]
                + result.stderr[-3000:]
            )

        if not output_dir.is_dir():
            raise FileNotFoundError(output_dir)

        print("RANKING TRAINING COMPLETED:", output_dir)

        return str(output_dir)

    @task
    def validate_ranking_artifacts(output_path):

        output_dir = Path(output_path)

        required_files = [
            "ranking_model.keras",
            "ranking_user_ids.npy",
            "ranking_movie_ids.npy",
            "ranking_scaler.joblib",
            "training_metrics.json"
        ]

        for filename in required_files:
            path = output_dir / filename
            if not path.is_file() or path.stat().st_size == 0:
                raise FileNotFoundError(path)

        model_path = output_dir / "ranking_model.keras"

        if not zipfile.is_zipfile(model_path):
            raise ValueError("Invalid Keras model archive")

        user_ids = np.load(
            output_dir / "ranking_user_ids.npy",
            allow_pickle=False
        )
        movie_ids = np.load(
            output_dir / "ranking_movie_ids.npy",
            allow_pickle=False
        )

        if len(user_ids) == 0 or len(movie_ids) == 0:
            raise ValueError("Empty ranking vocabulary")

        metrics = json.loads(
            (
                output_dir / "training_metrics.json"
            ).read_text(encoding="utf-8")
        )

        if metrics["status"] != "TRAINED_NOT_PROMOTED":
            raise ValueError("Unexpected training status")

        if metrics["smoke_test"] is not True:
            raise ValueError("Expected smoke test")

        if not (
            metrics["training_end_timestamp"]
            < metrics["validation_start_timestamp"]
        ):
            raise ValueError("Chronological boundary invalid")

        for name in ["accuracy", "auc", "pr_auc"]:
            value = float(metrics["validation_metrics"][name])
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Invalid metric: " + name)

        loss = float(metrics["validation_metrics"]["loss"])
        if not np.isfinite(loss) or loss < 0:
            raise ValueError("Invalid validation loss")

        print("RANKING ARTIFACT VALIDATION PASSED!")
        print("Training rows:", metrics["training_rows"])
        print("Validation rows:", metrics["validation_rows"])
        print("Validation AUC:",
              metrics["validation_metrics"]["auc"])
        print("Automatic promotion: DISABLED")

        return {
            "status": "PASS",
            "staging_dir": str(output_dir),
            "promotion_approved": False
        }

    project = validate_training_inputs()
    staged = train_ranking(project)
    validate_ranking_artifacts(staged)


ranking_retraining_smoke()
