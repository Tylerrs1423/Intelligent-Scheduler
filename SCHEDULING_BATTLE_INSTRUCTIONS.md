# 🎮 Scheduling Battle Simulator - Fun Testing Project

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.8 or higher
- Git
- Basic Python knowledge

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone [YOUR_REPO_URL]
   cd ai-foco
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up the database**
   ```bash
   # The database will be created automatically when you run the app
   # No additional setup needed!
   ```

## 🎯 Your Mission: Test the Scoring System!

### What You're Testing
The **CleanScheduler** has a sophisticated scoring system that decides where to place tasks. It considers:
- Time preferences (morning, afternoon, evening)
- Task priorities (1-6, where 6 is highest)
- Workload balance across days
- Task spacing and distribution
- Difficulty balance

### Your Task: Understand and Test the Scoring System

**Primary Goal**: Learn how the scoring system works and test different scenarios
**Optional Goal**: Create a fun visual battle simulator (if you want to make it fancy!)

## 📁 Project Structure

```
ai-foco/
├── app/
│   ├── routes/
│   │   └── events.py          # Main scheduling engine (2344 lines!)
│   ├── models.py              # Database models
│   ├── schemas.py             # Data validation
│   └── main.py               # FastAPI app
├── app/metaheuristic.py       # Test scenarios
└── requirements.txt           # Dependencies
```

## 🧪 How to Run the Scheduler

### Step 1: Run the Existing Test
First, let's see how the system currently works:

```bash
# Make sure you're in the ai-foco directory
cd ai-foco

# Activate your virtual environment
source env/bin/activate  # On Windows: env\Scripts\activate

# Run the existing test
python -m app.metaheuristic
```

**What this does:**
- Creates sample tasks (goals, workouts, study sessions)
- Runs them through the scheduling system
- Shows you the final schedule
- Displays debug information about scoring

**Expected output:** You'll see a lot of debug information showing how tasks are scored and scheduled, ending with a final schedule.

### Step 2: Understand What You're Seeing
The output will show:
- Task creation and priorities
- Slot scoring for each task
- Displacement logic when tasks conflict
- Final schedule with all tasks placed

## 🔍 Key Functions to Explore

### In `app/routes/events.py`:

1. **`_calculate_slot_score()`** - The main scoring function (around line 592)
   - This is where the magic happens!
   - Combines time preference, workload balance, spacing, etc.

2. **`_calculate_time_preference_score()`** - How time preferences are scored (around line 1062)
   - Scores how well a time slot matches the task's preferred time

3. **`_calculate_task_selection_priority()`** - How task priorities work (around line 863)
   - Determines which tasks get scheduled first

4. **`_displace_lower_priority_tasks()`** - How conflicts are resolved (around line 1382)
   - Handles when high-priority tasks need to displace lower-priority ones

### In `app/metaheuristic.py`:

1. **`test_hybrid_scheduler()`** - See how tasks are created and scheduled
2. **Look at the Quest objects** - Understand how tasks are defined

## 🎯 Your Testing Tasks

### Task 1: Basic Understanding (Required)
1. **Run the existing test** and understand the output
2. **Look at the debug prints** to see how scoring works
3. **Identify which tasks got scheduled where** and why

### Task 2: Modify and Test (Required)
Create a simple test script to experiment with different scenarios:

```python
# Create: app/test_scoring.py
from app.metaheuristic import test_hybrid_scheduler
from app.routes.events import CleanScheduler
from app.models import Quest, SchedulingFlexibility, PreferredTimeOfDay
from datetime import datetime, timedelta, time

def test_priority_scoring():
    """Test how different priorities affect scheduling"""
    print("Testing Priority Scoring...")
    # Create tasks with different priorities
    # Run them through the scheduler
    # See which ones get scheduled first

def test_time_preferences():
    """Test how time preferences affect scoring"""
    print("Testing Time Preferences...")
    # Create tasks that prefer different times
    # See how they get scored differently

def test_displacement():
    """Test how displacement works"""
    print("Testing Displacement...")
    # Create conflicting tasks
    # See how the system resolves conflicts

if __name__ == "__main__":
    test_priority_scoring()
    test_time_preferences()
    test_displacement()
```

### Task 3: Visual Battle Simulator (Optional - Only if you want to!)
If you want to make it fancy, create a visual battle simulator:

```python
# Create: app/demo/scheduler_battle.py
# This is completely optional - only do this if you want to make it visual!

def create_battle_simulator():
    """Create a fun visual demo of the scheduling system"""
    print("⚔️  SCHEDULING BATTLE ⚔️")
    # Add your creative visual elements here
    # Use emojis, progress bars, dramatic language
    # Show tasks competing for time slots
```

## 🎯 Specific Challenges to Test

### Challenge 1: Priority Battle
Create 3 tasks with priorities 6, 4, and 2. See how the system schedules them!

**What to look for:**
- Higher priority tasks should get scheduled first
- Lower priority tasks might get displaced
- Check the debug output to see the scoring

### Challenge 2: Time Preference War
Create tasks that prefer different times of day. Watch them compete!

**What to look for:**
- Tasks should prefer their specified time windows
- Check how the scoring changes for different time slots
- See if tasks get scheduled in their preferred times

### Challenge 3: Displacement Drama
Create a scenario where a high-priority task needs to displace a lower-priority one.

**What to look for:**
- The displacement logic should kick in
- Lower priority tasks should get rescheduled
- Check the debug output for displacement messages

### Challenge 4: Workload Balance
Create many tasks and see how the system distributes them across days.

**What to look for:**
- Tasks should be spread across multiple days
- No single day should be overloaded
- Check the workload balance scoring

## 💡 How to Modify and Test

### Step 1: Understand the Current System
1. **Run the existing test** multiple times
2. **Read the debug output** carefully
3. **Look at the code** in `app/routes/events.py`

### Step 2: Make Small Changes
1. **Modify task priorities** in `metaheuristic.py`
2. **Change time preferences** for tasks
3. **Add more tasks** to see how the system handles them

### Step 3: Test Your Changes
1. **Run your modified test**
2. **Compare the results** to the original
3. **Understand why** the scheduling changed

## 🔍 Debug Output Explained

When you run the scheduler, you'll see output like:
```
🔍 Looking for optimal slot for 'Gym Workout' (ID: 7)
🔍 Slot candidate: 2025-08-01 10:30:00 - 2025-08-01 12:00:00
🔍 Time preference score: 100.0 (expected window)
🔍 Slot score: 1050.2
🔍 PICKED: 2025-08-01 10:30:00 - 2025-08-01 12:00:00
```

**What this means:**
- The system is looking for a slot for "Gym Workout"
- It found a candidate slot from 10:30-12:00
- The time preference score is 100.0 (perfect match for expected time)
- The total slot score is 1050.2
- This slot was selected as the best option

## 🚨 Troubleshooting

### Common Issues:
- **Import errors**: Make sure you're in the right directory and virtual environment is activated
- **Database errors**: The system will create the database automatically
- **Module not found**: Make sure you've installed all requirements

### Getting Help:
- **Look at the debug output** - it tells you exactly what's happening
- **Check the existing `metaheuristic.py`** file for examples
- **The system has extensive debug prints** to help you understand

## 🎉 Success Criteria

You've successfully tested the scoring system if:
- ✅ You can run the existing test and understand the output
- ✅ You can modify task parameters and see how it affects scheduling
- ✅ You understand how priorities, time preferences, and displacement work
- ✅ You can explain why tasks get scheduled in certain slots

## 🏆 Bonus (Optional)

If you want to make it fancy:
- **Add visual elements** with emojis and formatting
- **Create a tournament** - multiple rounds of scheduling battles
- **Add user input** - let users create their own tasks
- **Visualize the schedule** with ASCII art

---

**Focus on understanding the scoring system first! The visual stuff is just for fun if you want to make it fancy. The most important thing is that you understand how the scheduling algorithm works and can test different scenarios.** 🚀 