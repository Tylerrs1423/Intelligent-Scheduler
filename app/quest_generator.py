import random
from datetime import datetime
from .models import Quest, QuestType, QuestStatus, User
from .database import get_db
from sqlalchemy.orm import Session

def generate_quest(task):
    """
    Generate a quest dictionary based on a Task object.
    Task should have: title, description, and optional deadline.
    """
    title_templates = [
        "Speed-run {title} in 25 minutes",
        "Complete '{title}' before {deadline}",
        "Turn '{title}' into a legendary quest!",
        "No distractions: focus on '{title}' for 1 hour",
        "Finish '{title}' and earn your XP!",
        "Epic challenge: {title} by {deadline}",
        "{title}: The Ultimate Side Quest"
    ]
    desc_templates = [
        "You can do this! Stay focused and power through.",
        "Every hero needs a quest. Make this one count!",
        "Level up your productivity with this challenge.",
        "No monsters, just motivation. Go!",
        "XP awaits those who finish their quests!",
        "A true champion never gives up. Complete this for glory!",
        "This is your moment. Make it epic!"
    ]
    
    deadline = getattr(task, 'deadline', None) or "the end of the day"
    quest_title = random.choice(title_templates).format(title=task.title, deadline=deadline)
    quest_desc = random.choice(desc_templates)
    xp_reward = random.randint(10, 100)
    created_at = datetime.utcnow().isoformat()
    return {
        "title": quest_title,
        "description": quest_desc,
        "xp_reward": xp_reward,
        "created_at": created_at
    }

def generate_daily_quest(user_id: int, db: Session) -> Quest:
    """Generate a daily quest for a user with their custom tasks"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    
    # Get user's custom daily quest tasks
    daily_tasks = user.daily_quest_tasks or []
    
    # If no custom tasks set, use default ones
    if not daily_tasks:
        daily_tasks = [
            {"title": "Morning Exercise", "description": "Complete 30 minutes of physical activity"},
            {"title": "Mindfulness Practice", "description": "Meditate for 15 minutes"},
            {"title": "Learning Time", "description": "Spend 20 minutes learning something new"}
        ]
    
    # Limit to 4 tasks maximum
    daily_tasks = daily_tasks[:4]
    
    # Create quest description with all tasks
    task_descriptions = []
    for i, task in enumerate(daily_tasks, 1):
        task_descriptions.append(f"{i}. {task['title']}: {task['description']}")
    
    quest_description = "Complete all of the following daily tasks:\n" + "\n".join(task_descriptions)
    
    # Calculate deadline (end of current day)
    now = datetime.utcnow()
    deadline = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    quest = Quest(
        title=f"Daily Quest - {now.strftime('%B %d, %Y')}",
        description=quest_description,
        quest_type=QuestType.DAILY,
        xp_reward=100,  # Daily quests always give 100 XP
        deadline=deadline,
        owner_id=user_id,
        status=QuestStatus.PENDING,
        earliest_acceptance=now,
        earliest_completion=now
    )
    
    db.add(quest)
    db.commit()
    db.refresh(quest)
    
    return quest 