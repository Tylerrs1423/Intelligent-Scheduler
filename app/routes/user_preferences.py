from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import UserQuestPreference, User, MainDailyQuestTemplate, MainDailyQuestSubtaskTemplate, THEME_CATEGORIES
from ..schemas import UserQuestPreferenceIn, UserQuestPreferenceOut
from ..auth import get_current_user
from datetime import time
from ..services.scheduler import schedule_user_daily_quest
from typing import List
from pydantic import BaseModel, Field
import pytz

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
    preferred_daily_quest_time = None
    if data.preferred_daily_quest_time:
        try:
            preferred_daily_quest_time = time.fromisoformat(data.preferred_daily_quest_time)
        except Exception:
            raise HTTPException(status_code=400, detail="preferred_daily_quest_time must be in HH:MM format")
    old_time = pref.preferred_daily_quest_time if pref else None
    old_tz = pref.timezone if pref else None
    if pref:
        pref.preferred_daily_quest_time = preferred_daily_quest_time
        pref.theme_tags = data.theme_tags
        pref.goal_intent_paragraph = data.goal_intent_paragraph
        pref.enabled = data.enabled
        pref.timezone = data.timezone
        pref.preffered_difficulty = data.preffered_difficulty
        pref.user_intensity_profile = data.user_intensity_profile
    else:
        pref = UserQuestPreference(
            user_id=current_user.id,
            preferred_daily_quest_time=preferred_daily_quest_time,
            theme_tags=data.theme_tags,
            goal_intent_paragraph=data.goal_intent_paragraph,
            enabled=data.enabled,
            timezone=data.timezone,
            preffered_difficulty=data.preffered_difficulty,
            user_intensity_profile=data.user_intensity_profile
        )
        db.add(pref)
    db.commit()
    db.refresh(pref)
    # Only reschedule if preferred_daily_quest_time or timezone changed
    if (old_time != pref.preferred_daily_quest_time) or (old_tz != pref.timezone):
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
    old_time = pref.preferred_daily_quest_time
    old_tz = pref.timezone
    if data.preferred_daily_quest_time is not None:
        try:
            pref.preferred_daily_quest_time = time.fromisoformat(data.preferred_daily_quest_time)
        except Exception:
            raise HTTPException(status_code=400, detail="preferred_daily_quest_time must be in HH:MM format")
    if data.theme_tags is not None:
        pref.theme_tags = data.theme_tags
    if data.goal_intent_paragraph is not None:
        pref.goal_intent_paragraph = data.goal_intent_paragraph
    if data.enabled is not None:
        pref.enabled = data.enabled
    if data.timezone is not None:
        pref.timezone = data.timezone
    if data.preffered_difficulty is not None:
        pref.preffered_difficulty = data.preffered_difficulty
    if data.user_intensity_profile is not None:
        pref.user_intensity_profile = data.user_intensity_profile
    db.commit()
    db.refresh(pref)
    if (old_time != pref.preferred_daily_quest_time) or (old_tz != pref.timezone):
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

@router.patch("/user/preferences/intensity", response_model=UserQuestPreferenceOut)
def update_user_intensity_profile(new_intensity: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update the user's intensity profile."""
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        raise HTTPException(status_code=404, detail="No preferences set for this user")
    from app.models import UserIntensityProfile
    try:
        pref.user_intensity_profile = UserIntensityProfile(new_intensity)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid intensity profile. Must be one of: {[d.value for d in UserIntensityProfile]}")
    db.commit()
    db.refresh(pref)
    return pref

@router.get("/user/preferences/theme-tags", response_model=dict)
def get_theme_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all available theme categories"""
    return THEME_CATEGORIES

@router.get("/user/preferences/theme-tags/flat", response_model=List[str])
def get_all_theme_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all available theme tags as a flat list"""
    valid_tags = []
    for category, tags in THEME_CATEGORIES.items():
        valid_tags.extend(tags)
    return valid_tags

@router.get("/user/preferences/my-theme-tags", response_model=List[str])
def get_my_theme_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get user's selected theme tags"""
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        return []
    return pref.theme_tags or []

@router.post("/user/preferences/theme-tags/{theme_tag}")
def add_theme_tag(theme_tag: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Add a theme tag to user's preferences"""
    # Check if theme_tag exists in any of the categories
    valid_tags = []
    for category, tags in THEME_CATEGORIES.items():
        valid_tags.extend(tags)
    
    if theme_tag not in valid_tags:
        raise HTTPException(status_code=400, detail=f"Invalid theme tag. Must be one of: {valid_tags}")

    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserQuestPreference(
            user_id=current_user.id,
            theme_tags=[theme_tag],
            enabled=True
        )
        db.add(pref)
    else:
        if theme_tag not in pref.theme_tags:
            pref.theme_tags.append(theme_tag)

    db.commit()
    db.refresh(pref)
    return {"message": f"Theme tag '{theme_tag}' added successfully", "theme_tags": pref.theme_tags}

@router.delete("/user/preferences/theme-tags/{theme_tag}")
def remove_theme_tag(theme_tag: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Remove a theme tag from user's preferences"""
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref or not pref.theme_tags:
        raise HTTPException(status_code=404, detail="No theme tags found for this user")

    if theme_tag not in pref.theme_tags:
        raise HTTPException(status_code=404, detail=f"Theme tag '{theme_tag}' not found in user's preferences")

    pref.theme_tags.remove(theme_tag)
    db.commit()
    db.refresh(pref)
    return {"message": f"Theme tag '{theme_tag}' removed successfully", "theme_tags": pref.theme_tags}

class ThemeTagBatchIn(BaseModel):
    theme_tags: List[str] = Field(..., description="List of theme tags to add or remove")

@router.post("/user/preferences/theme-tags/batch-add")
def add_theme_tags_batch(data: ThemeTagBatchIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Add multiple theme tags to user's preferences in batch"""
    # Get all valid tags from THEME_CATEGORIES
    valid_tags = []
    for category, tags in THEME_CATEGORIES.items():
        valid_tags.extend(tags)
    
    # Validate all theme tags
    invalid_tags = [tag for tag in data.theme_tags if tag not in valid_tags]
    if invalid_tags:
        raise HTTPException(status_code=400, detail=f"Invalid theme tags: {invalid_tags}. Must be one of: {valid_tags}")

    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserQuestPreference(
            user_id=current_user.id,
            theme_tags=data.theme_tags,
            enabled=True
        )
        db.add(pref)
    else:
        if pref.theme_tags is None:
            pref.theme_tags = []
        # Add only tags that aren't already present
        for tag in data.theme_tags:
            if tag not in pref.theme_tags:
                pref.theme_tags.append(tag)

    db.commit()
    db.refresh(pref)
    return {"message": f"Added {len(data.theme_tags)} theme tags successfully", "theme_tags": pref.theme_tags}

@router.post("/user/preferences/theme-tags/batch-remove")
def remove_theme_tags_batch(data: ThemeTagBatchIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Remove multiple theme tags from user's preferences in batch"""
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref or not pref.theme_tags:
        raise HTTPException(status_code=404, detail="No theme tags found for this user")

    # Remove tags that exist in user's preferences
    removed_tags = []
    for tag in data.theme_tags:
        if tag in pref.theme_tags:
            pref.theme_tags.remove(tag)
            removed_tags.append(tag)

    if not removed_tags:
        raise HTTPException(status_code=404, detail="None of the specified theme tags were found in user's preferences")

    db.commit()
    db.refresh(pref)
    return {"message": f"Removed {len(removed_tags)} theme tags successfully", "removed_tags": removed_tags, "theme_tags": pref.theme_tags}

@router.put("/user/preferences/theme-tags/replace")
def replace_theme_tags(data: ThemeTagBatchIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Replace all theme tags with the provided list"""
    # Get all valid tags from THEME_CATEGORIES
    valid_tags = []
    for category, tags in THEME_CATEGORIES.items():
        valid_tags.extend(tags)
    
    # Validate all theme tags
    invalid_tags = [tag for tag in data.theme_tags if tag not in valid_tags]
    if invalid_tags:
        raise HTTPException(status_code=400, detail=f"Invalid theme tags: {invalid_tags}. Must be one of: {valid_tags}")

    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserQuestPreference(
            user_id=current_user.id,
            theme_tags=data.theme_tags,
            enabled=True
        )
        db.add(pref)
    else:
        pref.theme_tags = data.theme_tags

    db.commit()
    db.refresh(pref)
    return {"message": f"Replaced theme tags successfully", "theme_tags": pref.theme_tags}

class GoalIntentIn(BaseModel):
    goal_intent_paragraph: str = Field(..., max_length=150, description="User's goal intent paragraph (max 150 characters)")

@router.put("/user/preferences/goal-intent")
def update_goal_intent(data: GoalIntentIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Update the user's goal intent paragraph"""
    if len(data.goal_intent_paragraph) > 150:
        raise HTTPException(status_code=400, detail="Goal intent paragraph must be 150 characters or less")
    
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserQuestPreference(
            user_id=current_user.id,
            goal_intent_paragraph=data.goal_intent_paragraph,
            enabled=True
        )
        db.add(pref)
    else:
        pref.goal_intent_paragraph = data.goal_intent_paragraph
    
    db.commit()
    db.refresh(pref)
    return {"message": "Goal intent paragraph updated successfully", "goal_intent_paragraph": pref.goal_intent_paragraph}

@router.get("/user/preferences/goal-intent")
def get_goal_intent(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get the user's goal intent paragraph"""
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        return {"goal_intent_paragraph": None}
    return {"goal_intent_paragraph": pref.goal_intent_paragraph}

class QuestTimeRangeIn(BaseModel):
    start: str  # HH:MM
    end: str    # HH:MM

@router.post("/user/preferences/quest-times")
def add_preferred_quest_time(time_range: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Add a preferred quest time range"""
    # Validate time range format
    if not isinstance(time_range, dict) or "start" not in time_range or "end" not in time_range:
        raise HTTPException(status_code=400, detail="Time range must be a dict with 'start' and 'end' keys")

    try:
        # Validate time format (HH:MM)
        time.fromisoformat(time_range["start"])
        time.fromisoformat(time_range["end"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Time format must be HH:MM")

    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserQuestPreference(
            user_id=current_user.id,
            preferred_quest_times=[time_range],
            enabled=True
        )
        db.add(pref)
    else:
        if pref.preferred_quest_times is None:
            pref.preferred_quest_times = []
        pref.preferred_quest_times.append(time_range)

    db.commit()
    db.refresh(pref)
    return {"message": "Preferred quest time range added successfully", "preferred_quest_times": pref.preferred_quest_times}

@router.get("/user/preferences/quest-times", response_model=List[dict])
def get_preferred_quest_times(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get user's preferred quest time ranges"""
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    if not pref:
        return []
    return pref.preferred_quest_times or []

@router.delete("/user/preferences/quest-times", response_model=dict)
def remove_preferred_quest_time(
    time_range: QuestTimeRangeIn = Body(..., example={"start": "08:00", "end": "10:00"}),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a single preferred quest time range (interpreted in user's preferred timezone). Send JSON: {"start": "08:00", "end": "10:00"}"""
    pref = db.query(UserQuestPreference).filter(UserQuestPreference.user_id == current_user.id).first()
    tz_str = pref.timezone if pref and pref.timezone else 'UTC'
    try:
        user_tz = pytz.timezone(tz_str)
    except Exception:
        user_tz = pytz.UTC
    if not pref or not pref.preferred_quest_times:
        raise HTTPException(status_code=404, detail="No preferred quest times found for this user")
    try:
        start = time.fromisoformat(time_range.start)
        end = time.fromisoformat(time_range.end)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Time format must be HH:MM")
    # Remove the matching time range
    found = False
    for tr in pref.preferred_quest_times[:]:
        try:
            tr_start = time.fromisoformat(tr["start"])
            tr_end = time.fromisoformat(tr["end"])
            if tr_start == start and tr_end == end:
                pref.preferred_quest_times.remove(tr)
                found = True
                break
        except Exception:
            continue
    if not found:
        raise HTTPException(status_code=404, detail="Specified time range not found in user's preferences")
    db.commit()
    db.refresh(pref)
    return {"message": f"Preferred quest time range {time_range.start} to {time_range.end} (timezone: {tz_str}) removed successfully", "preferred_quest_times": pref.preferred_quest_times} 