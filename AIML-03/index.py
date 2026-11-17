import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "deployment"))

import gradio as gr
from fastapi.responses import RedirectResponse

import app as backend
import gradio_dashboard as dashboard

@backend.app.get("/", include_in_schema=False)
def home():
    return RedirectResponse(url="/ui/")

app = gr.mount_gradio_app(
    backend.app,
    dashboard.demo,
    path="/ui"
)
