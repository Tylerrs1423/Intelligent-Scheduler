"""Minimal Events API: list events, list by date, get available slots, and list events in a window."""

from typing import List
from datetime import datetime, date as _date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Event, User
from ..schemas import EventOut, EventCreate, EventUpdate
from ..auth import get_current_user
from ..scheduling import CleanScheduler, CleanTimeSlot, AVAILABLE, RESERVED
from ..scheduling.utils.slot_utils import replace_slot

router = APIRouter(tags=["events"])



# get events by date, whether it be a single day or a range of days
@router.get("/date")
async def get_events_by_date(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date: _date = Query(...),
):
    return db.query(Event).filter(Event.user_id == current_user.id, Event.start_time.between(date, date + timedelta(days=1))).order_by(Event.start_time.asc()).all()

@router.get("/date_range")
async def get_events_by_date_range(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    start_date: _date = Query(...),
    end_date: _date = Query(...),
):
    return db.query(Event).filter(Event.user_id == current_user.id, Event.start_time.between(start_date, end_date)).order_by(Event.start_time.asc()).all()

@router.get("/")
async def list_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Event).filter(Event.user_id == current_user.id).order_by(Event.start_time.asc()).all()

@router.get("/scheduler-slots")
async def get_scheduler_slots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get scheduler slots for the frontend to display timeslots."""
    
    slots = scheduler_service.get_scheduler_slots(current_user.id, db)
    if not slots:
        return {"slots": [], "message": "No scheduler available. Please set sleep preferences first."}
    
    # Convert slots to frontend-friendly format
    formatted_slots = []
    for slot in slots:
        if slot.occupant in ["AVAILABLE", "RESERVED", "BUFFER"]:
            formatted_slots.append({
                "start_time": slot.start.isoformat(),
                "end_time": slot.end.isoformat(),
                "occupant": slot.occupant,
                "status": "available" if slot.occupant == "AVAILABLE" else "occupied"
            })
        else:
            # This is an event object
            formatted_slots.append({
                "start_time": slot.start.isoformat(),
                "end_time": slot.end.isoformat(),
                "occupant": {
                    "type": "event",
                    "title": getattr(slot.occupant, 'title', 'Event'),
                    "id": getattr(slot.occupant, 'id', None),
                    "priority": getattr(slot.occupant, 'priority', 0)
                },
                "status": "occupied"
            })
    
    return {"slots": formatted_slots}

@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()

# Import scheduler service at module level to keep it in memory
from ..services.scheduler_service import scheduler_service
from ..models import PreferredTimeOfDay, SchedulingFlexibility

@router.post("/create")
async def create_event(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event_in: EventCreate = Body(...),
):
    
    # Validate flexible event requirements
    if event_in.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
        if event_in.start_time or event_in.end_time:
            raise HTTPException(
                status_code=400,
                detail="Flexible events cannot have start_time or end_time"
            )
        if not event_in.duration:
            raise HTTPException(
                status_code=400,
                detail="Flexible events must have a duration"
            )
    else:  # FIXED event
        if not event_in.start_time or not event_in.end_time:
            raise HTTPException(
                status_code=400,
                detail="Fixed events must have start_time and end_time"
            )
    
    # Get scheduler for user
    scheduler = scheduler_service.get_or_create_scheduler(current_user.id, db)
    if not scheduler:
        raise HTTPException(
            status_code=400, 
            detail="User must set sleep preferences before creating events"
        )
    
    
    # Create temporary event object for scheduling test
    temp_event = Event(
        user_id=current_user.id,
        title=event_in.title,
        description=event_in.description,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        scheduling_flexibility=event_in.scheduling_flexibility,
        priority=event_in.priority,
        buffer_before=event_in.buffer_before or 0,
        buffer_after=event_in.buffer_after or 0,
        is_auto_generated=False,
        source=None,
        source_id=None,
        earliest_start=None,
        latest_end=None,
        allowed_days=None,
        soft_start=None,  # Will be set by scheduler based on time_preference
        soft_end=None,    # Will be set by scheduler based on time_preference
        hard_start=None,
        hard_end=None,
        min_duration=event_in.duration,  # Use duration for flexible events
        max_duration=None,
        recurrence_rule=event_in.recurrence_rule,
        depends_on_event_id=event_in.depends_on_event_id,
        depends_on_quest_id=event_in.depends_on_quest_id,
        mood=event_in.mood,
        max_moves=event_in.max_moves or 0,
        moves_count=0,
        preferred_time_of_day=event_in.time_preference
    )
    
    # Try to schedule the event first
    success = scheduler_service.add_event_to_scheduler(current_user.id, temp_event, db)
    if not success:
        raise HTTPException(
            status_code=409, 
            detail="Cannot schedule event - conflicts with existing events or sleep time"
        )
    
    # If scheduling succeeded, save to database
    db.add(temp_event)
    db.commit()
    db.refresh(temp_event)
    
    new_event = temp_event

    return new_event

@router.put("/update/{event_id}")
async def update_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event_in: EventUpdate = Body(...),
):
    # Find the event
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Update only the fields that were provided
    if event_in.title is not None:
        event.title = event_in.title
    if event_in.description is not None:
        event.description = event_in.description
    if event_in.start_time is not None:
        event.start_time = event_in.start_time
    if event_in.end_time is not None:
        event.end_time = event_in.end_time
    if event_in.buffer_before is not None:
        event.buffer_before = event_in.buffer_before
    if event_in.buffer_after is not None:
        event.buffer_after = event_in.buffer_after
    
    db.commit()
    
    return {"success": True, "message": "Event updated"}

@router.delete("/delete/{event_id}")
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Find the event
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db.delete(event)
    db.commit()
    
    return {"success": True, "message": "Event deleted"}