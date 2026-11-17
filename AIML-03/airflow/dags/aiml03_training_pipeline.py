
import os
import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pendulum
from airflow.sdk import dag, task, get_current_context


@dag(
    dag_id="aiml03_retrieval_training_pipeline",
    start_date=pendulum.datetime(
        2026, 10, 22, tz="Asia/Kolkata"
    ),
    schedule="0 2 * * 0",
    catchup=False,
    max_active_runs=1,
    tags=["AIML-03", "training", "faiss"]
)
def retrieval_training_pipeline():

    @task
    def train_retrieval():

        project = Path(os.environ["AIML03_PROJECT_DIR"])

        config = json.loads(
            (project / "airflow" /
             "training_runner_config.json").read_text()
        )

        if config["mode"] != "smoke":
            raise ValueError("Only smoke mode is enabled")

        if config["promotion_enabled"] is not False:
            raise ValueError("Promotion must be disabled")

        context = get_current_context()
        run_id = context["run_id"]

        # Unique, reproducible folder name per DAG run
        run_hash = hashlib.sha256(
            run_id.encode()
        ).hexdigest()[:16]

        output_name = f"airflow_retrain_{run_hash}"
        staging_dir = project / "staging" / output_name

        if staging_dir.exists():
            raise FileExistsError(
                f"Staging directory already exists: {staging_dir}"
            )

        command = [
            config["training_python"],
            str(project / "training" / "train_retrieval.py"),
            "--project-dir", str(project),
            "--epochs", "1",
            "--smoke",
            "--output-name", output_name
        ]

        env = os.environ.copy()
        env["TF_USE_LEGACY_KERAS"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = "-1"

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Training failed:\n"
                + result.stdout[-1500:]
                + result.stderr[-3000:]
            )

        metrics_path = staging_dir / "training_metrics.json"

        if not metrics_path.exists():
            raise FileNotFoundError(metrics_path)

        metrics = json.loads(metrics_path.read_text())

        if (
            metrics["status"] != "TRAINED_NOT_PROMOTED"
            or metrics["smoke_test"] is not True
        ):
            raise ValueError("Unexpected training status")

        print("TRAINING COMPLETED:", staging_dir)
        print("Training interactions:",
              metrics["training_interactions"])

        return str(staging_dir)

    @task
    def rebuild_faiss(staging_path):

        project = Path(os.environ["AIML03_PROJECT_DIR"])
        staging_dir = Path(staging_path)
        output_dir = staging_dir / "faiss_index"

        config = json.loads(
            (project / "airflow" /
             "training_runner_config.json").read_text()
        )

        command = [
            config["training_python"],
            str(project / "training" / "rebuild_faiss.py"),
            "--staging-dir", str(staging_dir),
            "--output-dir", str(output_dir)
        ]

        env = os.environ.copy()
        env["TF_USE_LEGACY_KERAS"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = "-1"

        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            raise RuntimeError(
                "FAISS rebuilding failed:\n"
                + result.stdout[-1500:]
                + result.stderr[-3000:]
            )

        print("FAISS REBUILD COMPLETED:", output_dir)
        return str(output_dir)

    @task
    def validate_staging(index_path):

        import numpy as np
        import faiss

        index_dir = Path(index_path)
        staging_dir = index_dir.parent

        index = faiss.read_index(
            str(index_dir / "movie_embeddings.index")
        )

        indexed_ids = np.load(
            index_dir / "indexed_movie_ids.npy"
        )

        training_ids = np.load(
            staging_dir / "movie_ids.npy"
        )

        np.testing.assert_array_equal(
            indexed_ids, training_ids
        )

        assert index.ntotal == len(indexed_ids)
        assert index.d == 32
        assert index.ntotal > 0

        result = {
            "status": "PASS",
            "indexed_movies": int(index.ntotal),
            "embedding_dimension": int(index.d),
            "promotion_approved": False,
            "staging_dir": str(staging_dir)
        }

        print("STAGING VALIDATION:", result)
        print("NO PRODUCTION ARTIFACTS MODIFIED")

        return result

    staged = train_retrieval()
    index_dir = rebuild_faiss(staged)
    validate_staging(index_dir)


retrieval_training_pipeline()
