from fastapi import APIRouter
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse

from .db import SessionLocal

router = APIRouter(tags=["observability"])
instrumentator = Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics"],
    should_ignore_untemplated=True,
)


@router.get("/ready")
def readiness(request: Request):
    db: Session = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "service": "opspilot-api"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "service": "opspilot-api"})
    finally:
        db.close()
