from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .auth import get_current_user
from .models import TicketPriority, User
from .sla import SLA_MINUTES

router = APIRouter(prefix="/sla", tags=["sla"])


class SlaDefault(BaseModel):
    priority: TicketPriority
    response_minutes: int
    resolution_minutes: int


@router.get("/defaults", response_model=list[SlaDefault])
def sla_defaults(user: User = Depends(get_current_user)) -> list[SlaDefault]:
    return [
        SlaDefault(priority=priority, response_minutes=response, resolution_minutes=resolution)
        for priority, (response, resolution) in SLA_MINUTES.items()
    ]
