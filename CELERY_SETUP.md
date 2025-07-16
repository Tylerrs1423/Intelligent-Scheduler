# Celery Setup for AI Foco

This guide explains how to set up and run Celery with Beat for scheduling daily quests.

## Prerequisites

1. **Redis Server**: Make sure Redis is running on localhost:6379
2. **Dependencies**: Install pytz for timezone support
   ```bash
   pip install pytz
   ```

## Running Celery

You need to run two components:

### 1. Celery Worker
The worker processes the scheduled tasks:
```bash
python start_celery_worker.py
```

### 2. Celery Beat (Scheduler)
The beat scheduler triggers tasks at specified intervals:
```bash
python start_celery_beat.py
```

## How It Works

1. **Beat Schedule**: Runs every hour at minute 0 (e.g., 9:00, 10:00, 11:00...)
2. **Time Check**: For each user with enabled quest preferences:
   - Checks if current time matches their preferred time (within 5 minutes)
   - Uses user's timezone from preferences
3. **Quest Creation**: If it's the right time and no quest exists for today:
   - Creates a daily quest from their active template
   - Creates all subtasks from the template
   - Sets XP reward to 100

## User Preferences Required

Users need to set:
- `enabled`: True
- `preferred_time`: "HH:MM" format (e.g., "09:00")
- `timezone`: Valid timezone (e.g., "America/New_York", "Europe/London")
- An active daily quest template

## Testing

To test the system:
1. Create a user with quest preferences
2. Set preferred_time to a few minutes from now
3. Create an active daily quest template
4. Start both worker and beat
5. Wait for the scheduled time - a daily quest should be created

## Logs

Both worker and beat will log their activities. Look for:
- "Created daily quest for user X" - successful quest creation
- "Daily quest already exists" - quest already created today
- "User X has no preferred time" - missing user preferences 