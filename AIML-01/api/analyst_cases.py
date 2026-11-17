
"""Authenticated, persistent analyst case-management API."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from secrets import compare_digest
import sqlite3

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


STATUSES = {"OPEN", "INVESTIGATING", "RESOLVED"}
LABELS = {"FRAUD", "LEGITIMATE", "UNCERTAIN"}


class CaseCreate(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    fraud_probability: float = Field(ge=0, le=1)
    description: str = Field(default="", max_length=1000)


class CaseUpdate(BaseModel):
    status: str | None = None
    feedback_label: str | None = None
    analyst_note: str | None = Field(
        default=None, max_length=2000
    )


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(database_path, api_key):
    if not isinstance(api_key, str) or len(api_key) < 32:
        raise ValueError("Case API requires a strong secret")

    database_path = Path(database_path)

    if database_path.exists() and database_path.is_symlink():
        raise ValueError("Database symlink is not allowed")

    database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def database():
        connection = sqlite3.connect(
            str(database_path), timeout=10
        )
        connection.row_factory = sqlite3.Row

        try:
            yield connection
        finally:
            connection.close()

    with database() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS analyst_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                fraud_probability REAL NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'OPEN',
                feedback_label TEXT,
                analyst_note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        db.commit()

    app = FastAPI(
        title="AIML-01 Analyst Case Service",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def authenticate(x_api_key: str = Header(default="")):
        if not compare_digest(x_api_key, api_key):
            raise HTTPException(
                status_code=401,
                detail="Unauthorized"
            )

    def fetch_case(db, case_id):
        row = db.execute(
            "SELECT * FROM analyst_cases WHERE id = ?",
            (case_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404, detail="Case not found"
            )

        return dict(row)

    @app.get("/cases", dependencies=[Depends(authenticate)])
    def list_cases(limit: int = 50):
        if not 1 <= limit <= 100:
            raise HTTPException(
                status_code=422, detail="Invalid limit"
            )

        with database() as db:
            rows = db.execute(
                "SELECT * FROM analyst_cases "
                "ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return {"cases": [dict(row) for row in rows]}

    @app.post(
        "/cases",
        status_code=201,
        dependencies=[Depends(authenticate)]
    )
    def create_case(payload: CaseCreate):
        timestamp = now()

        try:
            with database() as db:
                with db:
                    cursor = db.execute("""
                        INSERT INTO analyst_cases (
                            event_id, fraud_probability,
                            description, status,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, 'OPEN', ?, ?)
                    """, (
                        payload.event_id,
                        payload.fraud_probability,
                        payload.description,
                        timestamp,
                        timestamp,
                    ))

                    case_id = cursor.lastrowid

                return fetch_case(db, case_id)

        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=409,
                detail="Event already has a case"
            )

    @app.get(
        "/cases/{case_id}",
        dependencies=[Depends(authenticate)]
    )
    def get_case(case_id: int):
        with database() as db:
            return fetch_case(db, case_id)

    @app.patch(
        "/cases/{case_id}",
        dependencies=[Depends(authenticate)]
    )
    def update_case(case_id: int, payload: CaseUpdate):
        changes = payload.model_dump(exclude_unset=True)

        if not changes:
            raise HTTPException(
                status_code=422,
                detail="No changes supplied"
            )

        if "status" in changes:
            if changes["status"] not in STATUSES:
                raise HTTPException(
                    status_code=422,
                    detail="Invalid case status"
                )

        if "feedback_label" in changes:
            if changes["feedback_label"] not in LABELS:
                raise HTTPException(
                    status_code=422,
                    detail="Invalid feedback label"
                )

        if (
            "analyst_note" in changes
            and changes["analyst_note"] is None
        ):
            raise HTTPException(
                status_code=422,
                detail="Analyst note cannot be null"
            )

        columns = ", ".join(
            f"{field} = ?" for field in changes
        )

        values = list(changes.values())

        with database() as db:
            with db:
                fetch_case(db, case_id)

                db.execute(
                    f"UPDATE analyst_cases SET {columns}, "
                    "updated_at = ? WHERE id = ?",
                    (*values, now(), case_id)
                )

            return fetch_case(db, case_id)

    return app
