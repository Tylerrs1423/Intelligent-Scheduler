from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import UserQuestPreference, User, MainDailyQuestTemplate, MainDailyQuestSubtaskTemplate
from ..schemas import UserQuestPreferenceIn, UserQuestPreferenceOut
from ..auth import get_current_user
from datetime import time
from ..services.scheduler import schedule_user_daily_quest

router = APIRouter(tags=["user-preferences"])

@router.get("/user/preferences", response_model=UserQuestPreferenceOut)
def get_user_preferences(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        raise HTTPException(status_code=404, detail="No preferences set for this user")
    return pref

@router.post("/user/preferences", response_model=UserQuestPreferenceOut)
def set_user_preferences(data: UserQuestPreferenceIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    # Parse preferred_time if provided
    preferred_time = None
    if data.preferred_time:
        try:
            preferred_time = time.fromisoformat(data.preferred_time)
        except Exception:
            raise HTTPException(status_code=400, detail="preferred_time must be in HH:MM format")
    old_time = pref.preferred_time if pref else None
    old_tz = pref.timezone if pref else None
    if pref:
        pref.preferred_time = preferred_time
        pref.theme_tags = data.theme_tags
        pref.enabled = data.enabled
        pref.timezone = data.timezone
    else:
        pref = UserQuestPreference(
            user_id=current_user.id,
            preferred_time=preferred_time,
            theme_tags=data.theme_tags,
            enabled=data.enabled,
            timezone=data.timezone
        )
        db.add(pref)
    db.commit()
    db.refresh(pref)
    # Only reschedule if preferred_time or timezone changed
    if (old_time != pref.preferred_time) or (old_tz != pref.timezone):
        # Check for active template with at least one subtask
        template = db.query(MainDailyQuestTemplate).filter(MainDailyQuestTemplate.user_id == current_user.id, MainDailyQuestTemplate.active == True).first()
        if template:
            subtasks = db.query(MainDailyQuestSubtaskTemplate).filter(MainDailyQuestSubtaskTemplate.template_id == template.id).all()
            if subtasks:
                schedule_user_daily_quest(db, current_user, pref)
            else:
                print(f"User {current_user.id} has no subtasks for their active daily quest template. Not scheduling daily quest.")
        else:
            print(f"User {current_user.id} has no active daily quest template. Not scheduling daily quest.")
    if not pref:
        raise HTTPException(status_code=500, detail="Failed to set user preferences")
    return pref

@router.patch("/user/preferences", response_model=UserQuestPreferenceOut)
def patch_user_preferences(data: UserQuestPreferenceIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        raise HTTPException(status_code=404, detail="No preferences set for this user")
    old_time = pref.preferred_time
    old_tz = pref.timezone
    if data.preferred_time is not None:
        try:
            pref.preferred_time = time.fromisoformat(data.preferred_time)
        except Exception:
            raise HTTPException(status_code=400, detail="preferred_time must be in HH:MM format")
    if data.theme_tags is not None:
        pref.theme_tags = data.theme_tags
    if data.enabled is not None:
        pref.enabled = data.enabled
    if data.timezone is not None:
        pref.timezone = data.timezone
    db.commit()
    db.refresh(pref)
    # Only reschedule if preferred_time or timezone changed
    if (old_time != pref.preferred_time) or (old_tz != pref.timezone):
        # Check for active template with at least one subtask
        template = db.query(MainDailyQuestTemplate).filter(MainDailyQuestTemplate.user_id == current_user.id, MainDailyQuestTemplate.active == True).first()
        if template:
            subtasks = db.query(MainDailyQuestSubtaskTemplate).filter(MainDailyQuestSubtaskTemplate.template_id == template.id).all()
            if subtasks:
                schedule_user_daily_quest(db, current_user, pref)
            else:
                print(f"User {current_user.id} has no subtasks for their active daily quest template. Not scheduling daily quest.")
        else:
            print(f"User {current_user.id} has no active daily quest template. Not scheduling daily quest.")
    if not pref:
        raise HTTPException(status_code=500, detail="Failed to update user preferences")
    return pref 