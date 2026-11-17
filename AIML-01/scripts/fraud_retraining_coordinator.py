
"""Guarded retraining execution coordinator.

Approval references are workflow records, not authentication.
Production use requires authenticated authorization and scheduling.
No automatic incumbent promotion is implemented.
"""

from pathlib import Path
import sqlite3

from fraud_retraining_worker import train_challenger


def approve_request(database, request_id, approval_reference):
    if not isinstance(approval_reference, str) or not (
        8 <= len(approval_reference) <= 128
    ):
        raise ValueError("Explicit approval reference required")

    with sqlite3.connect(str(database), timeout=10) as db:
        db.execute("BEGIN IMMEDIATE")

        changed = db.execute("""
            UPDATE retraining_requests
            SET status = 'APPROVED'
            WHERE id = ? AND status = 'PENDING_APPROVAL'
        """, (request_id,)).rowcount

        if changed != 1:
            db.rollback()
            raise PermissionError(
                "Request missing or not pending approval"
            )

        db.commit()

    return {
        "request_id": request_id,
        "status": "APPROVED",
        "approval_reference": approval_reference,
    }


def execute_approved(
    database,
    request_id,
    dataset,
    contract,
    output,
    *,
    explicit_execution=False,
    rounds=12,
    protected_directory=None,
):
    if explicit_execution is not True:
        raise PermissionError("Explicit execution authorization required")

    output = Path(output).resolve()

    if protected_directory is not None:
        protected = Path(protected_directory).resolve()
        if output == protected or output.is_relative_to(protected):
            raise ValueError("Approved model directory is protected")

    with sqlite3.connect(str(database), timeout=10) as db:
        db.execute("BEGIN IMMEDIATE")

        changed = db.execute("""
            UPDATE retraining_requests
            SET status = 'RUNNING'
            WHERE id = ? AND status = 'APPROVED'
        """, (request_id,)).rowcount

        if changed != 1:
            db.rollback()
            raise PermissionError(
                "Request is not approved or already executed"
            )

        db.commit()

    try:
        report = train_challenger(
            dataset,
            contract,
            output,
            approved=True,
            rounds=rounds,
        )
    except Exception:
        with sqlite3.connect(str(database), timeout=10) as db:
            db.execute("""
                UPDATE retraining_requests
                SET status = 'FAILED_REVIEW_REQUIRED'
                WHERE id = ? AND status = 'RUNNING'
            """, (request_id,))
            db.commit()
        raise

    with sqlite3.connect(str(database), timeout=10) as db:
        db.execute("""
            UPDATE retraining_requests
            SET status = 'CHALLENGER_EVALUATED'
            WHERE id = ? AND status = 'RUNNING'
        """, (request_id,))
        db.commit()

    return {
        "request_id": request_id,
        "status": "CHALLENGER_EVALUATED",
        "validation_pr_auc": report["validation_pr_auc"],
        "model_promoted": False,
    }
