"""
Simple Celery Tasks for AI Foco
Just for testing basic quest generation
"""

from celery import current_task
from sqlalchemy.orm import Session
import logging

from .celery_app import celery_app
from .database import SessionLocal
from .models import User, Quest, QuestStatus, QuestType
from .quest_generator import generate_quest_for_user

# Set up logging
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def generate_simple_quest(self, user_id: int, quest_type: str = "regular"):
    """
    Generate a simple quest for a user.
    This is just for testing Celery setup.
    """
    logger.info(f"🎯 Starting simple quest generation for user {user_id}, type: {quest_type}")
    
    try:
        db = SessionLocal()
        
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User {user_id} not found")
            return {"status": "error", "message": "User not found"}
        
        # Generate quest
        quest = generate_quest_for_user(user_id, quest_type, db)
        
        logger.info(f"✅ Generated {quest_type} quest '{quest.title}' for user {user_id}")
        return {
            "status": "success",
            "user_id": user_id,
            "quest_id": quest.id,
            "quest_title": quest.title,
            "quest_type": quest_type
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating quest for user {user_id}: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close() 