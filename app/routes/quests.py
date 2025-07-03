from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from ..database import get_db
from ..models import Quest, Task, User, QuestStatus
from ..schemas import QuestCreate, QuestUpdate, QuestOut, QuestCompletionResponse, LevelProgress
from ..auth import verify_token_with_role
from ..quest_generator import generate_quest
from ..leveling import get_quest_xp_reward, add_xp_to_user, get_level_progress

router = APIRouter(tags=["quests"])

# Helper to get current user object
def get_current_user(token_data: dict = Depends(verify_token_with_role), db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == token_data["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def validate_quest_timing(quest: Quest, action: str):
    """Validate quest timing constraints"""
    now = datetime.utcnow()
    
    if action == "accept":
        # Check if quest can be accepted now
        if quest.earliest_acceptance_time and now < quest.earliest_acceptance_time:
            raise HTTPException(
                status_code=400, 
                detail=f"Quest cannot be accepted before {quest.earliest_acceptance_time}"
            )
        
        if quest.acceptance_deadline and now > quest.acceptance_deadline:
            raise HTTPException(
                status_code=400, 
                detail=f"Quest acceptance deadline has passed: {quest.acceptance_deadline}"
            )
    
    elif action == "complete":
        # Check if quest can be completed now
        if quest.earliest_completion_time and now < quest.earliest_completion_time:
            raise HTTPException(
                status_code=400, 
                detail=f"Quest cannot be completed before {quest.earliest_completion_time}"
            )
        
        if quest.completion_deadline and now > quest.completion_deadline:
            raise HTTPException(
                status_code=400, 
                detail=f"Quest completion deadline has passed: {quest.completion_deadline}"
            )
        
        # For timed quests, check if time limit has expired
        if quest.is_timed and quest.accepted_at and quest.time_limit_minutes:
            time_limit_end = quest.accepted_at + timedelta(minutes=quest.time_limit_minutes)
            if now > time_limit_end:
                raise HTTPException(
                    status_code=400,
                    detail=f"Quest time limit has expired. You had {quest.time_limit_minutes} minutes to complete it."
                )

@router.post("/", response_model=QuestOut)
def create_quest(quest_data: QuestCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new quest (can be standalone or tied to a task)"""
    # If task_id is provided, verify task exists and is owned by user
    if quest_data.task_id:
        task = db.query(Task).filter(Task.id == quest_data.task_id, Task.owner_id == current_user.id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found or not owned by user")
    
    # Create quest with all the new fields
    quest = Quest(
        title=quest_data.title,
        description=quest_data.description,
        xp=quest_data.xp,
        task_id=quest_data.task_id,  # Can be None for standalone quests
        owner_id=current_user.id,
        
        # Quest type flags
        is_daily=quest_data.is_daily,
        is_hidden=quest_data.is_hidden,
        is_penalty=quest_data.is_penalty,
        is_timed=quest_data.is_timed,
        
        # Time-based fields
        earliest_completion_time=quest_data.earliest_completion_time,
        completion_deadline=quest_data.completion_deadline,
        earliest_acceptance_time=quest_data.earliest_acceptance_time,
        acceptance_deadline=quest_data.acceptance_deadline,
        time_limit_minutes=quest_data.time_limit_minutes,
        
        status=QuestStatus.PENDING
    )
    
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest

@router.post("/generate/{task_id}", response_model=QuestOut)
def create_quest_from_task(task_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generate a quest from an existing task"""
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not owned by user")
    
    # Generate quest data
    quest_data = generate_quest(task)
    
    # Create quest with generated data
    quest = Quest(
        title=quest_data["title"],
        description=quest_data["description"],
        xp=quest_data["xp"],
        task_id=task.id,  # Link to the specific task
        owner_id=current_user.id,
        status=QuestStatus.PENDING
    )
    
    db.add(quest)
    db.commit()
    db.refresh(quest)
    return quest

@router.get("/", response_model=List[QuestOut])
def list_quests(
    quest_type: str = None,  # Filter by quest type
    standalone_only: bool = False,  # Filter for quests not tied to tasks
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """List all quests for the current user with optional filtering"""
    query = db.query(Quest).filter(Quest.owner_id == current_user.id)
    
    # Filter for standalone quests (not tied to tasks)
    if standalone_only:
        query = query.filter(Quest.task_id.is_(None))
    
    # Filter by quest type if specified
    if quest_type:
        if quest_type == "daily":
            query = query.filter(Quest.is_daily == True)
        elif quest_type == "hidden":
            query = query.filter(Quest.is_hidden == True)
        elif quest_type == "penalty":
            query = query.filter(Quest.is_penalty == True)
        elif quest_type == "timed":
            query = query.filter(Quest.is_timed == True)
        elif quest_type == "regular":
            query = query.filter(
                Quest.is_daily == False,
                Quest.is_hidden == False,
                Quest.is_penalty == False,
                Quest.is_timed == False
            )
    
    return query.all()

@router.get("/{quest_id}", response_model=QuestOut)
def get_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get a specific quest"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quest

@router.post("/{quest_id}/accept", response_model=QuestOut)
def accept_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Accept a quest with time validation"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    if quest.status != QuestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Quest is not in pending status")
    
    # Validate timing constraints
    validate_quest_timing(quest, "accept")
    
    # Update quest status and timestamp
    quest.status = QuestStatus.ACCEPTED
    quest.accepted_at = datetime.utcnow()
    
    db.commit()
    db.refresh(quest)
    return quest

@router.post("/{quest_id}/reject", response_model=QuestOut)
def reject_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Reject a quest"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    if quest.status != QuestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Quest is not in pending status")
    
    quest.status = QuestStatus.REJECTED
    db.commit()
    db.refresh(quest)
    return quest

@router.post("/{quest_id}/complete", response_model=QuestCompletionResponse)
def complete_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Complete a quest with XP rewards and level progression"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    if quest.status != QuestStatus.ACCEPTED:
        raise HTTPException(status_code=400, detail="Quest must be accepted before completion")
    
    # Validate timing constraints
    validate_quest_timing(quest, "complete")
    
    # Calculate XP reward
    quest_type = "daily" if quest.is_daily else "regular"
    xp_reward = get_quest_xp_reward(quest.xp, quest_type, quest.is_penalty)
    
    # Update user XP and level
    old_xp = current_user.xp
    old_level = current_user.level
    
    new_xp, new_level, levels_gained = add_xp_to_user(current_user.xp, xp_reward)
    
    current_user.xp = new_xp
    current_user.level = new_level
    
    # Update quest status and timestamp
    quest.status = QuestStatus.COMPLETED
    quest.completed_at = datetime.utcnow()
    
    db.commit()
    db.refresh(quest)
    db.refresh(current_user)
    
    # Get level progress information
    level_progress = get_level_progress(new_xp)
    
    return QuestCompletionResponse(
        quest=QuestOut.from_orm(quest).dict(),
        xp_gained=xp_reward,
        levels_gained=levels_gained,
        new_xp=new_xp,
        new_level=new_level,
        level_progress=LevelProgress(**level_progress)
    )

@router.get("/daily/available", response_model=List[QuestOut])
def get_available_daily_quests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get available daily quests for the current user"""
    now = datetime.utcnow()
    
    # Get daily quests that are pending and within acceptance time window
    daily_quests = db.query(Quest).filter(
        Quest.owner_id == current_user.id,
        Quest.is_daily == True,
        Quest.status == QuestStatus.PENDING
    ).all()
    
    # Filter by timing constraints
    available_quests = []
    for quest in daily_quests:
        try:
            validate_quest_timing(quest, "accept")
            available_quests.append(quest)
        except HTTPException:
            # Skip quests that don't meet timing requirements
            continue
    
    return available_quests

@router.get("/penalty/active", response_model=List[QuestOut])
def get_active_penalty_quests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get active penalty quests for the current user"""
    return db.query(Quest).filter(
        Quest.owner_id == current_user.id,
        Quest.is_penalty == True,
        Quest.status.in_([QuestStatus.PENDING, QuestStatus.ACCEPTED])
    ).all()

@router.get("/standalone/available", response_model=List[QuestOut])
def get_standalone_quests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get standalone quests (not tied to tasks) for the current user"""
    return db.query(Quest).filter(
        Quest.owner_id == current_user.id,
        Quest.task_id.is_(None),
        Quest.status == QuestStatus.PENDING
    ).all() 