#!/usr/bin/env python3
"""
Simple launcher script for AI Foco API.
Run this from the root directory to start the application.
"""

import uvicorn
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the FastAPI app
from app.main import app

if __name__ == "__main__":
    print("🚀 Starting AI Foco API with auto-reload...")
    print("📖 API Documentation: http://localhost:8000/docs")
    print("🔍 Health Check: http://localhost:8000/health")
    print("🔄 Auto-reload is ENABLED - changes will automatically restart the server")
    print("🛑 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    # Use import string format for reload to work properly
    uvicorn.run(
        "app.main:app",  # This is the import string format
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],  # Watch the app directory for changes
        log_level="info"
    ) 