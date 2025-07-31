# app/routes/google_oauth.py
import os
import traceback
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from requests_oauthlib import OAuth2Session

from app.database import get_db
from app.models import User, GoogleOAuthToken, Event, SchedulingFlexibility, SourceType
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.auth import get_current_user

logger = logging.getLogger(__name__)

# Load these from your environment or .env
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/auth/google/callback"

AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

SCOPE = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

router = APIRouter()

@router.get("/auth/google/login")
def login_via_google():
    google = OAuth2Session(GOOGLE_CLIENT_ID, scope=SCOPE, redirect_uri=REDIRECT_URI)
    auth_url, _ = google.authorization_url(
        AUTHORIZATION_BASE_URL,
        access_type="offline",
        prompt="consent",
    )
    return RedirectResponse(auth_url)

@router.post("/calendar/webhook")
async def google_calendar_webhook(request: Request, db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
   
    headers = request.headers
    channel_id = headers.get("X-Goog-Channel-Id")
    resource_state = headers.get("X-Goog-Resource-State")
    channel = db.query(GoogleCalendarChannel).filter_by(channel_id=channel_id).first()
    if channel:
        from app.routes.google_oauth import sync_google_calendar_events
        background_tasks.add_task(sync_google_calendar_events, user_id=channel.user_id, db=db)
    return JSONResponse(status_code=200, content={"message": "Received"})

# Register webhook after OAuth login
def register_google_calendar_webhook(user, google_token, db: Session):
    creds = Credentials(
        token=google_token.access_token,
        refresh_token=google_token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        ],
    )
    service = build("calendar", "v3", credentials=creds)
    channel_id = str(uuid.uuid4())
    webhook_url = os.getenv("WEBHOOK_URL", "https://yourdomain.com/calendar/webhook")
    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": webhook_url,
    }
    response = service.events().watch(calendarId="primary", body=body).execute()
    # Store channel_id and user mapping
    expiration = response.get("expiration")
    resource_id = response.get("resourceId")
    channel = GoogleCalendarChannel(
        user_id=user.id,
        channel_id=channel_id,
        resource_id=resource_id,
        expiration=datetime.utcfromtimestamp(int(expiration) / 1000) if expiration else None,
    )
    db.add(channel)
    db.commit()

# Update OAuth callback to register webhook after login
@router.get("/auth/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        google = OAuth2Session(GOOGLE_CLIENT_ID, redirect_uri=REDIRECT_URI)
        
        # 1) Exchange code for token
        token = google.fetch_token(
            TOKEN_URL,
            client_secret=GOOGLE_CLIENT_SECRET,
            authorization_response=str(request.url),
        )

        # 2) Fetch user info
        resp = google.get(USER_INFO_URL)
        resp.raise_for_status()  # Raise if HTTP error
        
        user_info = resp.json()

        email = user_info.get("email")
        name = user_info.get("name")
        expires_at = token.get("expires_at")

        if not email:
            raise HTTPException(status_code=400, detail="No email returned from Google")

        # 3) Upsert user in DB
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                username=email.split("@")[0],
                email=email,
                name=name,
                is_active=True,
                role="user"  # or UserRole.USER if using Enum
            )
            db.add(user)
            db.flush()  # Assigns user.id for foreign key usage

        # 4) Upsert GoogleOAuthToken for the user
        google_token = db.query(GoogleOAuthToken).filter(GoogleOAuthToken.user_id == user.id).first()
        token_expiry_datetime = datetime.utcfromtimestamp(expires_at) if expires_at else None

        if google_token:
            google_token.access_token = token.get("access_token")
            google_token.refresh_token = token.get("refresh_token")
            google_token.token_expiry = token_expiry_datetime
        else:
            google_token = GoogleOAuthToken(
                user_id=user.id,
                access_token=token.get("access_token"),
                refresh_token=token.get("refresh_token"),
                token_expiry=token_expiry_datetime,
            )
            db.add(google_token)

        db.commit()

        # 5) Redirect to your app's custom scheme or return JSON
        return RedirectResponse(f"aifoco://auth/callback?email={email}")

    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Exception in Google OAuth callback:\n{tb}")
        print(tb)  # Also print to console immediately
        return JSONResponse(status_code=500, content={"detail": f"Internal Server Error: {str(e)}"})

@router.post("/calendar/sync")
def sync_google_calendar_events(user_id: int = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Use user_id (from webhook) or current_user (from authenticated user)
    if user_id is not None:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = current_user
    # 1. Get user's Google OAuth token
    google_token = db.query(GoogleOAuthToken).filter(GoogleOAuthToken.user_id == user.id).first()
    if not google_token:
        raise HTTPException(status_code=401, detail="No Google OAuth token found for user.")

    creds = Credentials(
        token=google_token.access_token,
        refresh_token=google_token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=[
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events.readonly",
        ],
    )
    service = build("calendar", "v3", credentials=creds)

    now = datetime.utcnow()
    month_later = now + timedelta(days=30)
    events_result = (
        service.events().list(
            calendarId="primary",
            timeMin=now.isoformat() + "Z",
            timeMax=month_later.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    )
    google_events = events_result.get("items", [])

    added = 0
    for g_event in google_events:
        g_id = g_event.get("id")
        g_title = g_event.get("summary", "(No Title)")
        g_desc = g_event.get("description", "")
        g_start = g_event["start"].get("dateTime") or g_event["start"].get("date")
        g_end = g_event["end"].get("dateTime") or g_event["end"].get("date")
        if not g_start or not g_end:
            continue
        start_dt = datetime.fromisoformat(g_start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(g_end.replace("Z", "+00:00"))
        # Avoid duplicates: check if event with this google event id already exists
        existing = db.query(Event).filter(Event.user_id == user.id, Event.source == SourceType.MANUAL, Event.source_id == g_id).first()
        if existing:
            continue
        # Add as fixed event
        event = Event(
            user_id=user.id,
            title=g_title,
            description=g_desc,
            start_time=start_dt,
            end_time=end_dt,
            scheduling_flexibility=SchedulingFlexibility.FIXED,
            source=SourceType.MANUAL,  # Or a new SourceType.GOOGLE if you want
            source_id=g_id,
        )
        db.add(event)
        added += 1
    db.commit()
    return {"added": added, "total_fetched": len(google_events)}
