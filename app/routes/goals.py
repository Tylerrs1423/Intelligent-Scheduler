from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Goal, User
from ..schemas import GoalCreate, GoalUpdate, GoalOut
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
    db_goal = Goal(
        title=goal.title,
        description=goal.description,
        owner_id=current_user.id
    )
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    
    # Update goal creation statistics
    from ..leveling import update_user_stats_on_goal_created
    update_user_stats_on_goal_created(current_user.id)
    
    return db_goal

@router.get("/", response_model=List[GoalOut])
def read_goals(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all goals for the current user"""
    goals = db.query(Goal).filter(Goal.owner_id == current_user.id).all()
    return goals

@router.get("/{goal_id}", response_model=GoalOut)
def read_goal(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get a specific goal"""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.owner_id == current_user.id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal

@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, goal_update: GoalUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update a goal"""
    pass

@router.delete("/{goal_id}")
def delete_goal(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a goal"""
    pass

# QUEST GENERATION DISABLED - This endpoint is kept for compatibility but does not generate quests
@router.post("/{goal_id}/generate_quest")
def generate_quest_for_goal(goal_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pass