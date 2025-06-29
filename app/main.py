'''
from enum import Enum
from pydantic import BaseModel, validator
from fastapi import Query, Header, HTTPException, Depends, FastAPI
from datetime import time
import re
import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from fastapi import Request
from fastapi.responses import RedirectResponse



load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")



app = FastAPI()




class Mood(str,Enum):
    happy = "happy"
    sad = "sad"
    embarassed = "embarassed"
    angry = "angry"
    anxious = "anxious"
    stressed = "stressed"

class MoodChart(BaseModel):
    mood: Mood
    note: str

class Task(BaseModel):
    title: str
    description: str | None = None
    datetime: time

    @validator("datetime", pre=True)
    def validate_time_format(cls, v):
        if isinstance(v, str):
            if not re.match(r"^\d{2}:\d{2}$",v):
                raise ValueError("Time must be in HH:MM format")
        return v



taskDict = {}
moodDict = {}
moodsChart = []


def verify_token(x_token: str = Header(...)):
    if x_token not in moodDict:
        raise HTTPException(status_code=401, detail="No user exists")
    return x_token

@app.put("/login/")
async def login(username: str):
    if username in moodDict:
        raise HTTPException(status_code=400, detail="User already exists")
    moodDict[username] = []
    taskDict[username] = []
    return {"message" : f"{username} logged in!"}

@app.get("/task/")
async def getAllTasks(user: str = Depends(verify_token)):
    return taskDict[user]

@app.post("/task/")
async def addTask(task: Task, user: str = Depends(verify_token)):
    taskDict[user].append(task)
    return {"message": "Task added", "task": task}




@app.get("/mood/")
async def getMood(user: str = Depends(verify_token)):
    return moodDict[user]

@app.post("/mood/")
async def addMood(moodChart: MoodChart, user: str = Depends(verify_token)):
    moodDict[user].append(moodChart)
    return {"message": "Mood added!", "total_entries": len(moodDict[user])}

'''






'''

@app.get('/login/google')
async def login_via_google(request: Request):
    google = oauth.create_client('google')
    redirect_uri = f"http://localhost:8000{request.url_for('authorize_google')}"
    return await google.authorize_redirect(request, redirect_uri)

@app.get('/auth/google/callback', name="authorize_google")
async def authorize_google(request):
    google = oauth.create_client('google')
    token = await google.authorize_access_token(request)
    userinfo = await google.parse_id_token(request,token)
    return {"token" : token, "user": userinfo}


class Rarity(str,Enum):
    common = "common"
    uncommon = "uncommon"
    rare = "rare"
    legendary = "legendary"
    foci = "foci"
    

class Treasure(BaseModel):
    name: str
    value: float
    rarity: Rarity

app = FastAPI()


treasures = []


def verify_api_key(api_key: str = Query(...)):
    if api_key != "secret":
        raise HTTPException(status_code=403, detail="Invalid API key")

def verify_token(x_token: str = Header(...)):
    if x_token != "secret":
        raise HTTPException(status_code=401, detail="Invalid Token")

@app.put("/treasures/")
async def addTreasure(treasure: Treasure, auth: None = Depends(verify_token)):
    treasures.append(treasure)
    return {"message" : "Treasure added", "treasure" : len(treasures)-1}

@app.put("/treasures/{treasure_id}")
async def updateTreasure(treasure_id:int, treasure:Treasure):
    if len(treasures) - 1 >= treasure_id:
        treasures[treasure_id] = treasure
        return {"message" : "Updated", "treasure" : treasure_id}
    return {"message": "Doesn't Exist"}

@app.get("/treasures/")
async def getAllTreasures(auth: None = Depends(verify_token), auth2: None = Depends(verify_api_key)):
    return treasures

@app.get("/treasures/{treasure_id}")
async def getTreasureByID(treasure_id: int, auth: None = Depends(verify_token), auth2: None = Depends(verify_api_key)):
   return treasures[treasure_id]


@app.delete("/treasures/{treasure_id}")
async def deleteTreasure(treasure_id: int):
    if 0 <= treasure_id < len(treasures):
        deleted = treasures.pop(treasure_id)
        return {"message" : "Deleted", "treasure" : deleted}
    return {"message": "Doesn't Exist"}
'''