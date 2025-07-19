"""
Quest Generator Service

This module contains logic for generating quests, including AI-based, template-based, or custom quest creation.
"""

from app.models import (
    Quest, Goal, User, QuestStatus, QuestType, QuestDifficulty, QuestSubtask,
    MainDailyQuestTemplate, MainDailyQuestSubtaskTemplate
)
from app.schemas import QuestCreate, QuestOut, QuestTimeRangeIn
from app.database import get_db
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
import logging
from app.services.gpt_wrapper import gpt_completion

logger = logging.getLogger(__name__)

def get_existing_quests_for_day(user: User, db: Session, target_date: datetime = None) -> List[dict]:
    """
    Get all existing quests for a specific day to include in the prompt.
    Returns a list of quests with their times and theme tags.
    """
    if target_date is None:
        target_date = datetime.utcnow()
    
    # Get the start and end of the target date
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Query for quests that are scheduled for this day
    existing_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.status.in_([QuestStatus.PENDING, QuestStatus.ACCEPTED]),
        Quest.deadline >= start_of_day,
        Quest.deadline <= end_of_day
    ).all()
    
    # Also check for scheduled tasks
    from app.models import ScheduledTask
    scheduled_tasks = db.query(ScheduledTask).filter(
        ScheduledTask.user_id == user.id,
        ScheduledTask.active == True,
        ScheduledTask.scheduled_for >= start_of_day,
        ScheduledTask.scheduled_for <= end_of_day
    ).all()
    
    quest_list = []
    
    # Add quests
    for quest in existing_quests:
        if quest.deadline:
            # Calculate the start time based on deadline and time limit
            start_time = quest.deadline
            if quest.time_limit_minutes:
                start_time = quest.deadline - timedelta(minutes=quest.time_limit_minutes)
            
            quest_list.append({
                "title": quest.title,
                "start": start_time.strftime('%H:%M'),
                "end": quest.deadline.strftime('%H:%M'),
                "tags": quest.theme_tags or []
            })
    
    # Add scheduled tasks
    for task in scheduled_tasks:
        task_start = task.scheduled_for
        task_end = task.scheduled_for + timedelta(minutes=30)  # Assume 30 minutes
        
        quest_list.append({
            "title": f"Scheduled Task",
            "start": task_start.strftime('%H:%M'),
            "end": task_end.strftime('%H:%M'),
            "tags": ["scheduled"]
        })
    
    # Sort by start time
    quest_list.sort(key=lambda x: x['start'])
    
    return quest_list





def generate_quest_from_preferences(
    user: User,
    db: Session,
    theme_tags: List[str],
    difficulty: Optional[QuestDifficulty] = None,
    target_date: datetime = None
) -> str:
    """
    Generate a quest using GPT based on user preferences.
    Checks for existing quests to avoid time conflicts.
    Returns the generated quest text (you can later parse/structure this as needed).
    """
    if difficulty is None and user.quest_preference:
        difficulty = user.quest_preference.preffered_difficulty or "Tier 2"
    elif difficulty is None:
        difficulty = "Tier 2"

    # Get existing quests for the day
    existing_quests = get_existing_quests_for_day(user, db, target_date)
    
    # Format existing quests for the prompt
    existing_quests_str = ""
    if existing_quests:
        existing_quests_str = f"[\n"
        for quest in existing_quests:
            tags_str = ', '.join(quest['tags']) if quest['tags'] else 'general'
            existing_quests_str += f"  {{ \"title\": \"{quest['title']}\", \"start\": \"{quest['start']}\", \"end\": \"{quest['end']}\", \"tags\": [{tags_str}] }},\n"
        existing_quests_str = existing_quests_str.rstrip(',\n') + "\n]"
    else:
        existing_quests_str = "[]"



    tags_str = ', '.join(theme_tags) if theme_tags else "general"
    timezone = getattr(user.quest_preference, 'timezone', None) or "UTC"

    prompt = (
        f"Create 1-3 smart productivity quests for a user, based on their schedule and existing quests.\n\n"
        f"### Existing Quests Today:\n"
        f"{existing_quests_str}\n\n"
        f"### User Goal Themes:\n"
        f"{tags_str}\n\n"
        f"### What To Do:\n"
        f"- Create 1–3 new quests that don't overlap with existing ones\n"
        f"- Each quest should have a title, description, estimated duration, theme tags, and scheduled start time\n"
        f"- Avoid duplicating existing themes too much\n"
        f"- You may vary quest types (focus, fun, light, challenging)\n"
        f"- Surprise is encouraged, but must be helpful\n\n"
        f"### Output Format:\n"
        f"[\n"
        f"  {{\n"
        f"    \"title\": \"Midday Reset Walk\",\n"
        f"    \"description\": \"Take a walk to reset your focus and get steps in.\",\n"
        f"    \"tags\": [\"fitness\", \"clarity\"],\n"
        f"    \"duration\": 30,\n"
        f"    \"scheduled_start\": \"13:00\"\n"
        f"  }}\n"
        f"]"
    )

    logger.debug(f"Quest Generation Prompt: {prompt}")
    quest_text = gpt_completion(prompt)
    return quest_text

