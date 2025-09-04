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

@router.get("/{event_id}")
async def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()

@router.post("/create")
async def create_event(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    event_in: EventCreate = Body(...),
):
    # Create scheduler instance covering a reasonable window around the event
    window_start = min(event_in.start_time, datetime.utcnow()) - timedelta(days=7)
    window_end = max(event_in.end_time, event_in.start_time) + timedelta(days=30)
    scheduler = CleanScheduler(window_start=window_start, window_end=window_end)
    
    # Load existing fixed events into scheduler timeline
    scheduler.load_fixed_events(db)
    
    # Create a Quest-like object for the scheduler
    from app.models import Quest, QuestStatus, QuestCategory, QuestType, QuestDifficulty
    quest = Quest(
        title=event_in.title,
        description=event_in.description,
        status=QuestStatus.PENDING,
        category=QuestCategory.WORK,  # Default category
        quest_type=QuestType.SINGLE,
        difficulty=QuestDifficulty.MEDIUM,  # Default difficulty
        priority=event_in.priority,
        buffer_before=event_in.buffer_before,
        buffer_after=event_in.buffer_after,
        user_id=current_user.id
    )
    
    # Let the scheduler handle ALL scheduling logic
    from app.models import SchedulingFlexibility
    if event_in.scheduling_flexibility == SchedulingFlexibility.FIXED:
        # For fixed events, try to schedule at exact time
        duration = event_in.end_time - event_in.start_time
        scheduled_slots = scheduler.schedule_task_at_exact_time(
            quest, event_in.start_time, duration, event_in.end_time
        )
        
        if not scheduled_slots:
            raise HTTPException(
                status_code=409, 
                detail="Cannot schedule event at requested time - conflicts with existing events"
            )
    else:
        # For flexible events, let scheduler find optimal time
        duration = event_in.end_time - event_in.start_time
        scheduled_slots = scheduler.schedule_task_with_buffers(quest, duration)
        
        if not scheduled_slots:
            raise HTTPException(
                status_code=409, 
                detail="Cannot find available time slot for this event"
            )
    
    # Get the actual scheduled times from the scheduler
    task_slot = next((slot for slot in scheduled_slots if slot.occupant == quest), None)
    if not task_slot:
        raise HTTPException(status_code=500, detail="Scheduler failed to create task slot")
    
    # Create the event with the scheduler-determined times
    new_event = Event(
        user_id=current_user.id,
        title=event_in.title,
        description=event_in.description,
        start_time=task_slot.start,
        end_time=task_slot.end,
        scheduling_flexibility=event_in.scheduling_flexibility,
        priority=event_in.priority,
        buffer_before=event_in.buffer_before,
        buffer_after=event_in.buffer_after,
    )

    db.add(new_event)
    db.commit()
    db.refresh(new_event)

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