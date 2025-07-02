import random
from datetime import datetime

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
    xp = random.randint(10, 100)
    created_at = datetime.utcnow().isoformat()
    return {
        "title": quest_title,
        "description": quest_desc,
        "xp": xp,
        "created_at": created_at
    } 