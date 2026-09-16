import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from .db import SessionLocal
from .models import TestCaseResult, TestRun

router = APIRouter(prefix="/test-center", tags=["test-center"])


class TestCaseIn(BaseModel):
    node_id: str = Field(min_length=1, max_length=500)
    name: str = Field(min_length=1, max_length=500)
    file_path: str | None = Field(default=None, max_length=500)
    class_name: str | None = Field(default=None, max_length=255)
    status: str = Field(min_length=1, max_length=30)
    duration_ms: int = Field(default=0, ge=0)
    message: str | None = None


class TestRunIn(BaseModel):
    suite: str = Field(default="pytest", max_length=100)
    commit_sha: str | None = Field(default=None, max_length=64)
    branch: str | None = Field(default=None, max_length=255)
    environment: str = Field(default="local", max_length=100)
    status: str = Field(default="passed", max_length=30)
    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    tests: list[TestCaseIn] = Field(default_factory=list)


def _run_dict(run: TestRun) -> dict:
    return {
        "id": str(run.id),
        "suite": run.suite,
        "commit_sha": run.commit_sha,
        "branch": run.branch,
        "environment": run.environment,
        "status": run.status,
        "total": run.total,
        "passed": run.passed,
        "failed": run.failed,
        "skipped": run.skipped,
        "errors": run.errors,
        "duration_ms": run.duration_ms,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
    }


@router.get("/summary")
def test_center_summary() -> dict:
    with SessionLocal() as db:
        runs = list(db.scalars(select(TestRun).order_by(TestRun.created_at.desc()).limit(20)).all())
        latest = runs[0] if runs else None
        return {
            "latest_run": _run_dict(latest) if latest else None,
            "runs_count": len(runs),
            "totals": {
                "passed": sum(run.passed for run in runs),
                "failed": sum(run.failed for run in runs),
                "skipped": sum(run.skipped for run in runs),
                "errors": sum(run.errors for run in runs),
            },
        }


@router.get("/runs")
def list_test_runs(limit: int = 50, offset: int = 0) -> list[dict]:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    with SessionLocal() as db:
        runs = db.scalars(select(TestRun).order_by(TestRun.created_at.desc()).offset(offset).limit(limit)).all()
        return [_run_dict(run) for run in runs]


@router.get("/runs/{run_id}")
def get_test_run(run_id: uuid.UUID) -> dict:
    with SessionLocal() as db:
        run = db.get(TestRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Test run not found")
        tests = db.scalars(select(TestCaseResult).where(TestCaseResult.run_id == run.id).order_by(TestCaseResult.file_path, TestCaseResult.node_id)).all()
        data = _run_dict(run)
        data["tests"] = [
            {
                "id": str(test.id),
                "node_id": test.node_id,
                "name": test.name,
                "file_path": test.file_path,
                "class_name": test.class_name,
                "status": test.status,
                "duration_ms": test.duration_ms,
                "message": test.message,
            }
            for test in tests
        ]
        return data


@router.post("/runs", status_code=201)
def create_test_run(payload: TestRunIn, x_test_center_token: str | None = Header(default=None)) -> dict:
    expected = os.getenv("TEST_CENTER_INGEST_TOKEN", "opspilot-test-center-dev")
    if x_test_center_token != expected:
        raise HTTPException(status_code=401, detail="Invalid test center token")

    with SessionLocal() as db:
        run = TestRun(
            suite=payload.suite,
            commit_sha=payload.commit_sha,
            branch=payload.branch,
            environment=payload.environment,
            status=payload.status,
            total=payload.total,
            passed=payload.passed,
            failed=payload.failed,
            skipped=payload.skipped,
            errors=payload.errors,
            duration_ms=payload.duration_ms,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
        )
        db.add(run)
        db.flush()
        for item in payload.tests:
            db.add(TestCaseResult(run_id=run.id, **item.model_dump()))
        db.commit()
        db.refresh(run)
        return _run_dict(run) | {"tests_saved": len(payload.tests)}
