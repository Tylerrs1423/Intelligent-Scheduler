from fastapi import FastAPI
from fastapi.security import HTTPBearer
from app.database import engine
from app.models import Base
from app.routes import users, events, schedule

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="AI Foco API",
    description="A FastAPI application with JWT Bearer authentication, refresh tokens, and role-based authorization",
    version="1.0.0"
)

# Include routers
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(schedule.router, prefix="/schedule", tags=["schedule"])

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
