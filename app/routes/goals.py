from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Goal, User, Subgoal, GoalStatus
from ..schemas import GoalCreate, GoalUpdate, GoalOut, SubgoalCreate, SubgoalOut
from ..auth import verify_token_with_role
# from ..quest_generator import generate_quest  # REMOVED: Quest generation disabled

router = APIRouter(tags=["goals"])

# Helper to get current user object
def get_current_user(token_data: dict = Depends(verify_token_with_role), db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == token_data["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=GoalOut)
def create_goal(goal: GoalCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new goal"""
    from datetime import timedelta
    db_goal = Goal(
        title=goal.title,
        description=goal.description,
        user_id=current_user.id,
        priority=goal.priority if goal.priority is not None else 2,
        status=goal.status if goal.status is not None else None,
        due_date=goal.due_date,
        estimated_duration=timedelta(minutes=goal.estimated_duration_minutes) if goal.estimated_duration_minutes is not None else None
    )
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)

    if goal.subgoals:
        for subgoal_data in goal.subgoals:
            subgoal = Subgoal(
                title=subgoal_data.title,
                description=subgoal_data.description,
                goal_id=db_goal.id
            )
            db.add(subgoal)
        db.commit()

    # Update goal creation statistics
    from ..leveling import update_user_stats_on_goal_created
    update_user_stats_on_goal_created(current_user.id)

    # Query subgoals to attach to db_goal for response
    db.refresh(db_goal)
    db_goal.subgoals = db.query(Subgoal).filter(Subgoal.goal_id == db_goal.id).all()
    return db_goal

@router.get("/", response_model=List[GoalOut])
def read_goals(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all goals for the current user"""
    goals = db.query(Goal).filter(Goal.user_id == current_user.id).all()
    return goals

@router.get("/{goal_id}", response_model=GoalOut)
def read_goal(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get a specific goal"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal

@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, goal_update: GoalUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update a goal"""
    from datetime import timedelta
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    if goal_update.title is not None:
        goal.title = goal_update.title
    if goal_update.description is not None:
        goal.description = goal_update.description
    if goal_update.priority is not None:
        goal.priority = goal_update.priority
    if goal_update.status is not None:
        goal.status = goal_update.status
    if goal_update.due_date is not None:
        goal.due_date = goal_update.due_date
    if goal_update.estimated_duration_minutes is not None:
        goal.estimated_duration = timedelta(minutes=goal_update.estimated_duration_minutes)
    db.commit()
    db.refresh(goal)
    goal.subgoals = db.query(Subgoal).filter(Subgoal.goal_id == goal.id).all()
    return goal

@router.delete("/{goal_id}")
def delete_goal(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a goal and its subgoals"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db.delete(goal)
    db.commit()
    return {"detail": "Goal deleted"}

@router.post("/{goal_id}/subgoals", response_model=SubgoalOut)
def create_subgoal(goal_id: int, subgoal: SubgoalCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a subgoal for a goal"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    db_subgoal = Subgoal(
        title=subgoal.title,
        description=subgoal.description,
        goal_id=goal_id
    )
    db.add(db_subgoal)
    db.commit()
    db.refresh(db_subgoal)
    return db_subgoal

@router.put("/subgoals/{subgoal_id}", response_model=SubgoalOut)
def update_subgoal(subgoal_id: int, subgoal_update: SubgoalCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update a subgoal"""
    subgoal = db.query(Subgoal).join(Goal).filter(Subgoal.id == subgoal_id, Goal.user_id == current_user.id).first()
    if not subgoal:
        raise HTTPException(status_code=404, detail="Subgoal not found")
    subgoal.title = subgoal_update.title
    subgoal.description = subgoal_update.description
    db.commit()
    db.refresh(subgoal)
    return subgoal

@router.delete("/subgoals/{subgoal_id}")
def delete_subgoal(subgoal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a subgoal"""
    subgoal = db.query(Subgoal).join(Goal).filter(Subgoal.id == subgoal_id, Goal.user_id == current_user.id).first()
    if not subgoal:
        raise HTTPException(status_code=404, detail="Subgoal not found")
    db.delete(subgoal)
    db.commit()
    return {"detail": "Subgoal deleted"}

@router.post("/{goal_id}/complete", response_model=GoalOut)
def complete_goal(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark a goal as completed (status=COMPLETED)"""
    from datetime import datetime
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    goal.status = GoalStatus.COMPLETED
    goal.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(goal)
    goal.subgoals = db.query(Subgoal).filter(Subgoal.goal_id == goal.id).all()
    return goal

@router.post("/subgoals/{subgoal_id}/complete", response_model=SubgoalOut)
def complete_subgoal(subgoal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark a subgoal as completed (is_completed=True). If all subgoals for the parent goal are completed, mark the goal as COMPLETED."""
    from datetime import datetime
    subgoal = db.query(Subgoal).join(Goal).filter(Subgoal.id == subgoal_id, Goal.user_id == current_user.id).first()
    if not subgoal:
        raise HTTPException(status_code=404, detail="Subgoal not found")
    subgoal.is_completed = True
    db.commit()
    db.refresh(subgoal)

    # Check if all subgoals for the parent goal are completed
    all_done = db.query(Subgoal).filter(Subgoal.goal_id == subgoal.goal_id, Subgoal.is_completed == False).count() == 0
    if all_done:
        goal = db.query(Goal).filter(Goal.id == subgoal.goal_id).first()
        if goal:
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = datetime.utcnow()
            db.commit()
    return subgoal

# QUEST GENERATION DISABLED - This endpoint is kept for compatibility but does not generate quests
@router.post("/{goal_id}/generate_quest")
def generate_quest_for_goal(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pass