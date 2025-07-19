from app.models import User, UserQuestPreference, QuestDifficulty
from app.schemas import QuestTimeRangeIn
from app.services.quest_generator import generate_quest_from_preferences
from sqlalchemy.orm import Session
from app.database import get_db

# Create a real SQLAlchemy User and UserQuestPreference instance (not committed to DB)
def mock_user():
    user = User(id=1)
    pref = UserQuestPreference(
        preffered_difficulty=QuestDifficulty.TIER_2,
        timezone="America/New_York"
    )
    user.quest_preference = pref
    return user

if __name__ == "__main__":
    user = mock_user()
    db: Session = next(get_db())
    theme_tags = ["Fitness", "Productivity"]
    preferred_times = [QuestTimeRangeIn(start="08:00", end="10:00")]
    result = generate_quest_from_preferences(user, db, theme_tags, preferred_times)
    print("\n--- GPT Generated Quest ---\n")
    print(result) 