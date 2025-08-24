"""
Schedule API endpoints for frontend
"""

from typing import List
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, User, SchedulingFlexibility
from ..schemas import EventOut, EventCreate, EventUpdate
from ..auth import get_current_user
from ..scheduling import CleanScheduler, CleanTimeSlot, AVAILABLE, RESERVED

router = APIRouter()

@router.get("/")
async def get_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: str = Query(..., description="Start of the date to get the schedule for"),
    end_date: str = Query(..., description="End of the date to get the schedule for"),
):
    """
    Get the schedule for a user for a given window
    Temporary solution: Recreates the scheduler every time
    """
    try:
        start = datetime.fromisoformat(f"{start_date}T00:00:00")
        end = datetime.fromisoformat(f"{end_date}T23:59:59")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    scheduler = CleanScheduler(
        window_start=start,
        window_end=end,
        user_sleep_start=current_user.sleep_start,
        user_sleep_end=current_user.sleep_end,
    )

    existing_events = db.query(Event).filter(
        Event.user_id == current_user.id,
        Event.start_time >= start,
        Event.end_time <= end,
        Event.scheduling_flexibility == SchedulingFlexibility.FIXED,
    ).all()

    return{
        "events": [
            {
                "id": event.id,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "title": event.title,
                "description": event.description,
                "scheduling_flexibility": event.scheduling_flexibility,
                "buffer_before": event.buffer_before,
                "buffer_after": event.buffer_after,
            }
            for event in existing_events
        ]
    }
    
