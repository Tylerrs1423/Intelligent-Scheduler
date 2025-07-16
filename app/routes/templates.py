from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import MainDailyQuestTemplate, MainDailyQuestSubtaskTemplate, MeasurementType, User
from ..schemas import DailyTemplateIn, DailyTemplateOut, SubtaskIn, SubtaskOut
from ..auth import get_current_user

router = APIRouter(tags=["templates"])

@router.post("/templates/daily", response_model=DailyTemplateOut)
def set_daily_template(template: DailyTemplateIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_template = db.query(MainDailyQuestTemplate).filter(MainDailyQuestTemplate.user_id == current_user.id, MainDailyQuestTemplate.active == True).first()
    if db_template:
        db_template.title = template.title
        db_template.description = template.description
        db_template.xp_reward = 100  # Always 100 XP for daily
    else:
        db_template = MainDailyQuestTemplate(
            user_id=current_user.id,
            title=template.title,
            description=template.description,
            xp_reward=100,  # Always 100 XP for daily
            active=True
        )
        db.add(db_template)
        
    db.commit()
    db.refresh(db_template)
    return db_template

@router.get("/templates/daily", response_model=DailyTemplateOut)
def get_daily_template(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_template = db.query(MainDailyQuestTemplate).filter(MainDailyQuestTemplate.user_id == current_user.id, MainDailyQuestTemplate.active == True).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="No daily template set yet for this user")
    return db_template

@router.post("/templates/daily/subtasks", response_model=SubtaskOut)
def add_subtask(subtask: SubtaskIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_template = db.query(MainDailyQuestTemplate).filter(MainDailyQuestTemplate.user_id == current_user.id, MainDailyQuestTemplate.active == True).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="No daily template set yet for this user")
    if len(db_template.subtasks) >= 3:
        raise HTTPException(status_code=400, detail="Maximum of 3 subtasks allowed")
    db_sub = MainDailyQuestSubtaskTemplate(
        template_id=db_template.id,
        title=subtask.title,
        measurement_type=subtask.measurement_type,
        goal_value=subtask.goal_value
    )
    db.add(db_sub)
    db.commit()
    db.refresh(db_sub)
    return db_sub

@router.patch("/templates/daily/subtasks/{sub_id}", response_model=SubtaskOut)
def update_subtask(sub_id: int = Path(..., gt=0), subtask: SubtaskIn = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_sub = db.query(MainDailyQuestSubtaskTemplate).join(MainDailyQuestTemplate).filter(
        MainDailyQuestSubtaskTemplate.id == sub_id,
        MainDailyQuestTemplate.user_id == current_user.id,
        MainDailyQuestTemplate.active == True
    ).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subtask not found for this user")
    if subtask.title:
        db_sub.title = subtask.title
    if subtask.measurement_type:
        db_sub.measurement_type = subtask.measurement_type
    db_sub.goal_value = subtask.goal_value
    db.commit()
    db.refresh(db_sub)
    return db_sub

@router.delete("/templates/daily/subtasks/{sub_id}")
def delete_subtask(sub_id: int = Path(..., gt=0), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_sub = db.query(MainDailyQuestSubtaskTemplate).join(MainDailyQuestTemplate).filter(
        MainDailyQuestSubtaskTemplate.id == sub_id,
        MainDailyQuestTemplate.user_id == current_user.id,
        MainDailyQuestTemplate.active == True
    ).first()
    if not db_sub:
        raise HTTPException(status_code=404, detail="Subtask not found for this user")
    db.delete(db_sub)
    db.commit()
    return {"detail": "Subtask deleted"} 