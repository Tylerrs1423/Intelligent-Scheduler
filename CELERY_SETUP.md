# 🚀 Celery Setup Guide for AI Foco

This guide will help you set up and use Celery for quest scheduling in your AI Foco project.

## 📋 What We Built

### Architecture Overview
```
📌 FastAPI App (run.py)
├── User registers / sets daily quest time
├── API endpoints for quest management
└── Celery task scheduling

📌 Celery Beat (start_celery_beat.py)
├── Runs on a schedule (every day at 9 AM)
├── Fires periodic tasks automatically
└── No manual intervention needed

📌 Redis (Message Broker)
├── Stores task messages in queues
├── Workers pull tasks from queues
└── Can also store task results

📌 Celery Workers (start_celery_worker.py)
├── Execute the actual tasks
├── Generate quests, save to DB
└── Can scale horizontally

📌 Database
├── Workers write quests to DB
├── FastAPI reads from DB
└── Clean separation of concerns
```

## 🛠️ Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Redis
**macOS:**
```bash
brew install redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get install redis-server
```

**Windows:**
Download from https://redis.io/download

## 🚀 Starting the System

You need to run **4 different processes** in separate terminal windows:

### Terminal 1: Start Redis
```bash
redis-server
```

### Terminal 2: Start Celery Worker
```bash
python start_celery_worker.py
```

### Terminal 3: Start Celery Beat (Scheduler)
```bash
python start_celery_beat.py
```

### Terminal 4: Start FastAPI
```bash
python run.py
```

## 🧪 Testing the Setup

Run the test script to verify everything is working:

```bash
python test_celery.py
```

This will:
- Test Celery connection to Redis
- Test manual quest generation
- Test daily quest generation

## 📁 File Structure

```
ai-foco/
├── app/
│   ├── celery_app.py          # Celery configuration
│   ├── celery_tasks.py        # Celery tasks (quest generation)
│   ├── routes/
│   │   ├── tasks.py           # Task management API (existing)
│   │   └── ...                # Other route files
│   └── ...
├── start_celery_worker.py     # Start Celery worker
├── start_celery_beat.py       # Start Celery Beat scheduler
├── test_celery.py             # Test Celery setup
└── CELERY_SETUP.md            # This file
```

## 🎯 How It Works

### 1. **Daily Quest Generation**
- Celery Beat runs every day at 9 AM
- Calls `generate_daily_quests_for_all_users` task
- This task finds all users with daily quest times set
- Schedules individual quest generation for each user

### 2. **Manual Quest Generation**
- User requests a quest via API
- FastAPI calls `generate_manual_quest.delay(user_id, quest_type)`
- Celery worker picks up the task
- Generates quest and saves to database

### 3. **Task Retry Logic**
- If a task fails, it automatically retries
- Daily quests: retry up to 3 times with 60-second delays
- Manual quests: retry up to 2 times with 30-second delays

## 🔧 Configuration

### Celery Settings (app/celery_app.py)
- **Broker**: Redis at localhost:6379
- **Result Backend**: Redis at localhost:6379
- **Timezone**: UTC
- **Task Serialization**: JSON
- **Worker Concurrency**: 2 processes
- **Queues**: quests, celery

### Beat Schedule
- **Daily Quest Generation**: Every day at 9:00 AM UTC
- **Task**: `generate_daily_quests_for_all_users`

## 🐛 Troubleshooting

### Redis Connection Issues
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Start Redis if not running
redis-server
```

### Celery Worker Issues
```bash
# Check worker status
celery -A app.celery_app inspect active

# Check task results
celery -A app.celery_app inspect stats
```

### Task Queue Issues
```bash
# Check queue length
celery -A app.celery_app inspect active_queues

# Purge all queues (if needed)
celery -A app.celery_app purge
```

## 📊 Monitoring

### Celery Flower (Optional)
Install and run Celery Flower for web-based monitoring:

```bash
pip install flower
celery -A app.celery_app flower
```

Then visit: http://localhost:5555

## 🔄 Next Steps

1. **Test the setup** with `python test_celery.py`
2. **Start all services** in separate terminals
3. **Create a user** via the API
4. **Set daily quest time** for the user
5. **Wait for 9 AM** or manually trigger quest generation
6. **Check the database** for generated quests

## 💡 Learning Points

- **Celery Beat** = Scheduler (when to run tasks)
- **Celery Workers** = Executors (how to run tasks)
- **Redis** = Message broker (where tasks are stored)
- **Tasks** = Functions that do the actual work
- **Queues** = Different types of tasks (quests, emails, etc.)

This setup gives you a robust, scalable system for quest generation that's much more reliable than APScheduler! 