from app.celery_app import celery_app
from app.models import ScheduledTask, TaskType
from datetime import datetime, timedelta
import pytz

def schedule_user_daily_quest(db, user, user_pref):
    # Cancel all previous active daily quest tasks
    db.query(ScheduledTask).filter_by(user_id=user.id, active=True, task_type=TaskType.DAILY_QUEST).update({"active": False})
    db.commit()

    # Find the last sent out daily quest
    from app.models import Quest
    last_quest = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.is_main_daily_quest == True,
        Quest.sent_out_at != None
    ).order_by(Quest.sent_out_at.desc()).first()

    tz = pytz.timezone(user_pref.timezone or 'UTC')
    now = datetime.now(tz)
    # Use hour and minute attributes from time object
    hour = user_pref.preferred_time.hour
    minute = user_pref.preferred_time.minute
    scheduled_local = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if scheduled_local <= now:
        scheduled_local += timedelta(days=1)

    # If a quest was sent out, ensure at least 24h gap
    if last_quest:
        next_allowed_time = last_quest.sent_out_at + timedelta(hours=24)
        # Convert next_allowed_time to user's timezone
        next_allowed_time_local = next_allowed_time.astimezone(tz)
        # Schedule for the later of preferred time or 24h after last sent
        scheduled_local = max(scheduled_local, next_allowed_time_local)

    scheduled_utc = scheduled_local.astimezone(pytz.UTC)

    # Schedule task
    result = celery_app.send_task(
        'app.celery_tasks.schedule.generate_daily_quest',
        args=[user.id],
        eta=scheduled_utc
    )

    # Track in DB
    scheduled_task = ScheduledTask(
        user_id=user.id,
        task_id=result.id,
        scheduled_for=scheduled_utc,
        task_type=TaskType.DAILY_QUEST,
        active=True
    )
    db.add(scheduled_task)
    db.commit() 