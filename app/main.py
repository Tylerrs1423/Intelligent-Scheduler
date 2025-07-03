from fastapi import FastAPI
from fastapi.security import HTTPBearer
from app.database import engine
from app.models import Base
from app.routes import users, protected, admin, tasks, quests

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
app.include_router(protected.router, prefix="/protected", tags=["protected"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(quests.router, prefix="/quests", tags=["quests"])
app.include_router(admin.router, tags=["admin"])

@app.get("/")
def read_root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to AI Foco API",
        "version": "1.0.0",
        "features": [
            "JWT Bearer Authentication with refresh tokens",
            "Role-based authorization (user/admin)",
            "Protected routes",
            "Admin dashboard and user management",
            "Task management (CRUD)",
            "Advanced Quest system with time-based mechanics",
            "Quest types: Regular, Daily, Hidden, Penalty, Timed",
            "Time-based quest constraints and deadlines",
            "Quest acceptance and completion validation",
            "XP and Leveling system (Level 1-500)",
            "Daily quests always give 100 XP",
            "Penalty quests can reduce XP and levels",
            "Progressive leveling difficulty"
        ],
        "endpoints": {
            "register": "PUT /users/register - Create a new user",
            "login": "POST /users/login - Login with JSON data",
            "refresh": "POST /users/refresh - Refresh access token",
            "profile": "GET /users/profile - Get user profile with level progress",
            "stats": "GET /users/stats - Get detailed user statistics and achievements",
            "tasks": "CRUD /tasks/ - Task management for users",
            "quests": "CRUD /quests/ - Quest management (standalone or task-based)",
            "quests_generate": "POST /quests/generate/{task_id} - Generate quest from task",
            "quests_daily": "GET /quests/daily/available - Available daily quests",
            "quests_penalty": "GET /quests/penalty/active - Active penalty quests",
            "quests_standalone": "GET /quests/standalone/available - Standalone quests",
            "protected": "GET /protected/ - Protected route requiring authentication",
            "admin_dashboard": "GET /admin/dashboard - Admin dashboard (admin only)",
            "admin_users": "GET /admin/users - View all users (admin only)",
            "admin_stats": "GET /admin/stats - User statistics with XP data (admin only)",
            "admin_system": "GET /admin/system-info - System information (admin only)"
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
