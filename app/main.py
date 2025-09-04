from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.database import engine
from app.models import Base
from app.routes import users, events, schedule, user_preferences
from app.services.scheduler_service import scheduler_service

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize schedulers for all users on startup
from app.database import SessionLocal
def initialize_schedulers():
    db = SessionLocal()
    try:
        scheduler_service.initialize_all_schedulers(db)
        print("✅ Schedulers initialized for all users")
    except Exception as e:
        print(f"❌ Failed to initialize schedulers: {e}")
    finally:
        db.close()

# Initialize on startup
initialize_schedulers()

# Create FastAPI app
app = FastAPI(
    title="AI Foco API",
    description="A FastAPI application with JWT Bearer authentication, refresh tokens, and role-based authorization",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Include routers
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(schedule.router, prefix="/schedule", tags=["schedule"])
app.include_router(user_preferences.router, prefix="/users", tags=["user-preferences"])

@app.get("/")
def read_root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to AI Foco API",
        "version": "1.0.0",
        "features": [
            "JWT Bearer Authentication with refresh tokens",
            "Protected routes",
            "Event management (CRUD)",
            "Schedule display and management"
        ],
        "endpoints": {
            "register": "POST /users/register - Create a new user",
            "login": "POST /users/login - Login with username and password",
            "refresh": "POST /users/refresh - Refresh access token",
            "profile": "GET /users/me/profile - Get user profile with level progress",
            "events": "CRUD /events/* - Event management (create, read, update, delete)",
            "schedule": "GET /schedule/ - Get formatted schedule for frontend"
        },
        "authentication": "Bearer token in Authorization header",
        "swagger_ui": "/docs - Interactive API documentation",
        "redoc": "/redoc - Alternative API documentation"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

# This allows running the app directly with: python -m app.main
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AI Foco API...")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🔍 Health Check: http://localhost:8000/health")
    # Use import string format for reload to work
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
