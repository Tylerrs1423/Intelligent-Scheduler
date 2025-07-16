from app.database import get_db
from app.models import Quest, User, ScheduledTask, MainDailyQuestTemplate, MainDailyQuestSubtaskTemplate, QuestSubtask, QuestType, QuestDifficulty, QuestStatus
from celery import current_task
from app.celery_app import celery_app
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
from app.leveling import update_user_stats_on_quest_failed, commit_user_stats_batch

logger = logging.getLogger(__name__)

def fail_stale_daily_quests(user: User, db: Session):
    """Fail any daily quests that are older than 24 hours and still pending"""
    stale_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.is_main_daily_quest == True,
        Quest.status == QuestStatus.PENDING,  # Only PENDING, not ACCEPTED
        Quest.created_at <= datetime.utcnow() - timedelta(hours=24)
    ).all()

    for quest in stale_quests:
        quest.status = QuestStatus.FAILED
        logger.info(f"Marked daily quest {quest.id} as FAILED for user {user.id} (24h timeout)")
        # Update stats for failed quest
        update_user_stats_on_quest_failed(user.id)

    if stale_quests:
        # Commit stats batch to database
        commit_user_stats_batch(db)
        db.commit()
        logger.info(f"Failed {len(stale_quests)} stale daily quests for user {user.id}")

@celery_app.task(name="app.celery_tasks.schedule.generate_daily_quest")
def generate_daily_quest(user_id: int):
    db: Session = next(get_db())
    task_id = current_task.request.id

    task_meta = db.query(ScheduledTask).filter_by(task_id=task_id).first()
    if not task_meta or not task_meta.active:
        logger.info(f"Skipping task {task_id} — inactive or not found")
        return

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        logger.error(f"User {user_id} not found")
        return

    # First, fail any stale daily quests (older than 24h)
    fail_stale_daily_quests(user, db)

    # Find active daily quest template for user
    template = db.query(MainDailyQuestTemplate).filter_by(user_id=user.id, active=True).first()
    if not template:
        logger.info(f"No active daily quest template for user {user.id}")
        return

    # Get subtasks for the template
    subtask_templates = db.query(MainDailyQuestSubtaskTemplate).filter_by(template_id=template.id).all()
    if not subtask_templates:
        logger.warning(f"No subtasks for template {template.id}, skipping quest creation for user {user.id}")
        return

    # Check if a daily quest already exists for today (UTC)
    today = datetime.utcnow().date()
    quest_exists = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.template_id == template.id,
        Quest.is_main_daily_quest == True,
        Quest.created_at >= datetime.combine(today, datetime.min.time()),
        Quest.created_at <= datetime.combine(today, datetime.max.time())
    ).first()
    if quest_exists:
        logger.info(f"Daily quest already exists for user {user.id} today")
        return

    # Create the main quest with 24-hour deadline
    now = datetime.utcnow()
    quest = Quest(
        title=template.title,
        description=template.description,
        xp_reward=100,  # Always 100 for daily quests
        owner_id=user.id,
        template_id=template.id,
        is_main_daily_quest=True,
        quest_type=QuestType.REGULAR,
        difficulty=QuestDifficulty.TIER_1,
        status=QuestStatus.PENDING,
        sent_out_at=now,
        deadline=now + timedelta(hours=24),
        time_limit_minutes=1440  # 24 hours in minutes
    )
    db.add(quest)
    db.flush()  # Get quest.id

    # Create subtasks from template
    for subtask_template in subtask_templates:
        subtask = QuestSubtask(
            title=subtask_template.title,
            description=None,
            quest_id=quest.id,
            measurement_type=subtask_template.measurement_type,
            goal_value=subtask_template.goal_value,
            is_completed=False
        )
        db.add(subtask)

    db.commit()
    logger.info(f"Created daily quest '{quest.title}' with {len(subtask_templates)} subtasks for user {user.id}")

    # Mark this task inactive since it's done
    task_meta.active = False
    db.commit()
    db.close() 