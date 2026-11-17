import os
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]

required = (
    "AIML01_DEPLOYMENT_API_KEY",
    "AIML01_CASES_API_KEY",
    "AIML01_CASE_DATABASE_PATH",
)

for name in required:
    if not os.environ.get(name):
        raise RuntimeError(f"Missing required environment variable: {name}")

# A Render persistent disk must be mounted at /var/data.
# Refuse to start if case data would be stored ephemerally.
case_database = Path(
    os.environ["AIML01_CASE_DATABASE_PATH"]
)

if case_database != Path("/var/data/cases.db"):
    raise RuntimeError(
        "Case database must be /var/data/cases.db"
    )

if not os.path.ismount("/var/data"):
    raise RuntimeError(
        "Persistent Render disk is not mounted at /var/data"
    )

os.environ["AIML01_PROJECT"] = str(PROJECT)
os.environ["AIML01_FEAST_REPO"] = str(PROJECT / "feast_repo")
os.environ["AIML01_FEAST_PYTHON"] = sys.executable
os.environ["AIML01_FEAST_SERVICE_URL"] = "http://127.0.0.1:8765"
os.environ["AIML01_ENABLE_DEMO_PREDICT"] = "1"
os.environ["AIML_FEAST_REPO"] = str(PROJECT / "feast_repo")
os.environ["AIML_FEAST_PORT"] = "8765"

port = int(os.environ.get("PORT", "10000"))
if not 1 <= port <= 65535:
    raise ValueError("Invalid Render PORT")

def ready():
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            return True
    except OSError:
        return False

feast = subprocess.Popen(
    [
        sys.executable,
        "-u",
        str(PROJECT / "api/feast_feature_service.py"),
    ],
    cwd=str(PROJECT / "api"),
    env=os.environ.copy(),
)

try:
    for _ in range(40):
        if ready():
            break
        if feast.poll() is not None:
            raise RuntimeError("Feast service exited during startup")
        time.sleep(0.5)

    if not ready():
        raise RuntimeError("Feast service did not become ready")

    command = [
        sys.executable, "-m", "uvicorn",
        "render_app:app",
        "--host", "0.0.0.0",
        "--port", str(port),
    ]

    result = subprocess.run(
        command,
        cwd=str(PROJECT / "deployment/render"),
        env=os.environ.copy(),
    )

    sys.exit(result.returncode)

finally:
    if feast.poll() is None:
        feast.terminate()
        try:
            feast.wait(timeout=10)
        except subprocess.TimeoutExpired:
            feast.kill()
            feast.wait()
