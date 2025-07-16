from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from ..database import get_db
from ..models import Quest, Goal, User, QuestStatus, QuestType, QuestSubtask
from ..schemas import QuestCreate, QuestUpdate, QuestOut, QuestCompletionResponse, LevelProgress
from ..auth import verify_token_with_role
# from ..quest_generator import generate_quest  # REMOVED: Quest generation disabled
from ..leveling import award_xp_and_level_up, get_level_progress, update_user_stats_on_quest_created, update_user_stats_on_quest_completed, commit_user_stats_batch

router = APIRouter(tags=["quests"])

# Helper to get current user object
def get_current_user(token_data: dict = Depends(verify_token_with_role), db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.username == token_data["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def validate_quest_timing(quest: Quest, action: str):
    """Validate quest timing constraints"""
    pass





@router.post("/", response_model=QuestOut)
def create_quest(quest_data: QuestCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new quest (can be standalone or tied to a goal)"""
    goal = None
    # Validate goal exists if goal_id is provided
    if quest_data.goal_id:
        goal = db.query(Goal).filter(Goal.id == quest_data.goal_id, Goal.owner_id == current_user.id).first()
        if not goal:
            raise HTTPException(status_code=404, detail="Goal not found")
    
    # Validate timed quest has required fields
    if quest_data.quest_type == QuestType.TIMED:
        if not quest_data.completion_deadline and not quest_data.time_limit_minutes:
            raise HTTPException(status_code=400, detail="Timed quests must have either a deadline or time limit")
    
    db_quest = Quest(
        title=quest_data.title,
        description=quest_data.description,
        xp_reward=quest_data.xp_reward,
        quest_type=quest_data.quest_type,
        deadline=quest_data.completion_deadline,
        time_limit_minutes=quest_data.time_limit_minutes,
        status=QuestStatus.STANDING_BY,
        owner_id=current_user.id
    )
    
    # Link quest to goal if provided
    if goal:
        db_quest.goals.append(goal)
    
    db.add(db_quest)
    db.commit()
    db.refresh(db_quest)
    
    # Update quest creation statistics
    update_user_stats_on_quest_created(current_user.id)
    
    return db_quest

@router.post("/{quest_id}/send_out", response_model=QuestOut)
def send_out_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send out a quest"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    # Prevent manually sending out main daily quests
    if quest.is_main_daily_quest:
        raise HTTPException(status_code=400, detail="Daily quests cannot be manually sent out - they are automatically scheduled")
    
    if quest.status != QuestStatus.STANDING_BY:
        raise HTTPException(status_code=400, detail="Quest is not standing by")
    
    quest.status = QuestStatus.PENDING
    quest.sent_out_at = datetime.now()
    db.commit()
    db.refresh(quest)
    return quest

@router.get("/", response_model=List[QuestOut])
def list_quests(
    quest_type: str = None,  # Filter by quest type
    standalone_only: bool = False,  # Filter for quests not tied to goals
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """List all quests for the current user with optional filtering"""
 
    return db.query(Quest).filter(Quest.owner_id == current_user.id, Quest.quest_type == quest_type).all()

@router.get("/{quest_id}", response_model=QuestOut)
def get_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get a specific quest"""
    return db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()

@router.post("/{quest_id}/accept", response_model=QuestOut)
def accept_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Accept a quest with time validation"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    # Prevent accepting main daily quests
    if quest.is_main_daily_quest:
        raise HTTPException(status_code=400, detail="Daily quests cannot be accepted - they are automatically sent out")
    
    if quest.status != QuestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Quest is not pending")
    
    if quest.time_limit_to_accept:
        if quest.sent_out_at is None:
            raise HTTPException(status_code=400, detail="Quest has not been sent out")
        if datetime.now() > quest.sent_out_at + timedelta(minutes=quest.time_limit_to_accept):
            raise HTTPException(status_code=400, detail="Quest acceptance deadline has passed")
    
    current_user.stats.total_quests_accepted += 1
    quest.status = QuestStatus.ACCEPTED
    quest.accepted_at = datetime.now()
    db.commit()
    db.refresh(quest)
    return quest
    

@router.post("/{quest_id}/reject", response_model=QuestOut)
def reject_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Reject a quest"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    if quest.is_main_daily_quest:
        raise HTTPException(status_code=400, detail="Daily quests cannot be accepted - they are automatically sent out")
    
    if quest.status != QuestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Quest is not pending")
    
    if quest.time_limit_to_accept:
        if quest.sent_out_at is None:
            raise HTTPException(status_code=400, detail="Quest has not been sent out")
        if datetime.now() > quest.sent_out_at + timedelta(minutes=quest.time_limit_to_accept):
            raise HTTPException(status_code=400, detail="Quest acceptance deadline has passed")
    
    current_user.stats.total_quests_rejected += 1
    quest.status = QuestStatus.REJECTED
    quest.rejected_at = datetime.now()
    db.commit()
    db.refresh(quest)
    return quest


@router.post("/{quest_id}/complete", response_model=QuestCompletionResponse)
def complete_quest(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Complete a quest with XP rewards and level progression"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    # Allow main daily quests to be completed from PENDING status
    if quest.is_main_daily_quest:
        if quest.status != QuestStatus.PENDING:
            raise HTTPException(status_code=400, detail="Daily quest is not pending")
    else:
        # Regular quests still need to be accepted first
        if quest.status != QuestStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="Quest is not accepted")
    
    if quest.time_limit_to_complete:
        if quest.sent_out_at is None:
            raise HTTPException(status_code=400, detail="Quest has not been sent out")
        if datetime.now() > quest.sent_out_at + timedelta(minutes=quest.time_limit_to_complete):
            raise HTTPException(status_code=400, detail="Quest completion deadline has passed")
    
    # Ensure user has stats
    if not current_user.stats:
        from ..models import UserStats
        user_stats = UserStats(user_id=current_user.id)
        db.add(user_stats)
        db.commit()
        db.refresh(current_user)
    
    # Award XP and handle level-ups
    levels_gained = award_xp_and_level_up(current_user.stats, quest.xp_reward)
    
    # Update quest status
    quest.status = QuestStatus.COMPLETED
    quest.completed_at = datetime.now()
    
    # Update statistics
    update_user_stats_on_quest_completed(current_user.id, quest.quest_type.value)
    
    # Commit stats batch to database
    commit_user_stats_batch(db)
    
    db.commit()
    db.refresh(quest)
    
    # Return completion response
    return {
        "quest": {
            "id": quest.id,
            "title": quest.title,
            "description": quest.description,
            "xp_reward": quest.xp_reward
        },
        "xp_gained": quest.xp_reward,
        "levels_gained": levels_gained,
        "new_xp": current_user.stats.xp_total,
        "new_level": current_user.stats.level,
        "level_progress": get_level_progress(current_user.stats)
    }

@router.get("/daily/available", response_model=List[QuestOut])
def get_available_daily_quests(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get available daily quests for the current user"""
    return []

@router.post("/{quest_id}/subtasks/{subtask_id}/complete")
def complete_subtask(quest_id: int, subtask_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Complete a specific subtask and check if the entire quest is complete"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    subtask = db.query(QuestSubtask).filter(QuestSubtask.id == subtask_id, QuestSubtask.quest_id == quest_id).first()
    if not subtask:
        raise HTTPException(status_code=404, detail="Subtask not found")
    
    if subtask.is_completed:
        raise HTTPException(status_code=400, detail="Subtask is already completed")
    
    # Mark subtask as completed
    subtask.is_completed = True
    subtask.completed_value = subtask.goal_value or 1  # Set to goal value or 1 if boolean
    
    # Check if all subtasks are completed
    all_subtasks = db.query(QuestSubtask).filter(QuestSubtask.quest_id == quest_id).all()
    all_completed = all(all_subtask.is_completed for all_subtask in all_subtasks)
    
    if all_completed:
        # Complete the entire quest
        if quest.is_main_daily_quest:
            if quest.status != QuestStatus.PENDING:
                raise HTTPException(status_code=400, detail="Daily quest is not pending")
        else:
            if quest.status != QuestStatus.ACCEPTED:
                raise HTTPException(status_code=400, detail="Quest is not accepted")
        
        # Ensure user has stats
        if not current_user.stats:
            from ..models import UserStats
            user_stats = UserStats(user_id=current_user.id)
            db.add(user_stats)
            db.commit()
            db.refresh(current_user)
        
        # Award XP and handle level-ups
        levels_gained = award_xp_and_level_up(current_user.stats, quest.xp_reward)
        
        # Update quest status
        quest.status = QuestStatus.COMPLETED
        quest.completed_at = datetime.now()
        
        # Update statistics
        update_user_stats_on_quest_completed(current_user.id, quest.quest_type.value)
        
        # Commit stats batch to database
        commit_user_stats_batch(db)
        
        db.commit()
        db.refresh(quest)
        
        return {
            "message": "Subtask completed and quest finished!",
            "quest_completed": True,
            "xp_gained": quest.xp_reward,
            "levels_gained": levels_gained,
            "new_xp": current_user.stats.xp_total,
            "new_level": current_user.stats.level,
            "level_progress": get_level_progress(current_user.stats)
        }
    else:
        db.commit()
        return {
            "message": "Subtask completed",
            "quest_completed": False,
            "completed_subtasks": sum(1 for s in all_subtasks if s.is_completed),
            "total_subtasks": len(all_subtasks)
        }

@router.post("/{quest_id}/subtasks/complete-all")
def complete_all_subtasks(quest_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Complete all subtasks for a quest at once"""
    quest = db.query(Quest).filter(Quest.id == quest_id, Quest.owner_id == current_user.id).first()
    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")
    
    # Check if quest can be completed
    if quest.is_main_daily_quest:
        if quest.status != QuestStatus.PENDING:
            raise HTTPException(status_code=400, detail="Daily quest is not pending")
    else:
        if quest.status != QuestStatus.ACCEPTED:
            raise HTTPException(status_code=400, detail="Quest is not accepted")
    
    # Get all subtasks
    subtasks = db.query(QuestSubtask).filter(QuestSubtask.quest_id == quest_id).all()
    if not subtasks:
        raise HTTPException(status_code=400, detail="Quest has no subtasks")
    
    # Mark all subtasks as completed
    for subtask in subtasks:
        if not subtask.is_completed:
            subtask.is_completed = True
            subtask.completed_value = subtask.goal_value or 1
    
    # Ensure user has stats
    if not current_user.stats:
        from ..models import UserStats
        user_stats = UserStats(user_id=current_user.id)
        db.add(user_stats)
        db.commit()
        db.refresh(current_user)
    
    # Award XP and handle level-ups
    levels_gained = award_xp_and_level_up(current_user.stats, quest.xp_reward)
    
    # Update quest status
    quest.status = QuestStatus.COMPLETED
    quest.completed_at = datetime.now()
    
    # Update statistics
    update_user_stats_on_quest_completed(current_user.id, quest.quest_type.value)
    
    # Commit stats batch to database
    commit_user_stats_batch(db)
    
    db.commit()
    db.refresh(quest)
    
    return {
        "message": "All subtasks completed and quest finished!",
        "quest_completed": True,
        "subtasks_completed": len(subtasks),
        "xp_gained": quest.xp_reward,
        "levels_gained": levels_gained,
        "new_xp": current_user.stats.xp_total,
        "new_level": current_user.stats.level,
        "level_progress": get_level_progress(current_user.stats)
    }

