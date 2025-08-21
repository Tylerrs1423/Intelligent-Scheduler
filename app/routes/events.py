"""Minimal Events API: list events, list by date, get available slots, and list events in a window."""

from typing import List
from datetime import datetime, date as _date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, User
from ..schemas import EventOut
from ..auth import get_current_user
from ..scheduling import CleanScheduler, CleanTimeSlot, AVAILABLE, RESERVED
from ..scheduling.utils.slot_utils import replace_slot

router = APIRouter(tags=["events"])


@router.get("/", response_model=List[EventOut])
async def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Event).filter(Event.user_id == current_user.id).order_by(Event.start_time.asc()).all()

@