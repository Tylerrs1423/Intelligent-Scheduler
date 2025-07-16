#!/usr/bin/env python3
"""
Start Celery Beat for AI Foco daily quest scheduling
"""

import os
import sys
from app.celery_app import celery_app

if __name__ == "__main__":
    print("Starting Celery Beat for AI Foco...")
    print("This will schedule daily quests based on user preferences")
    print("Press Ctrl+C to stop")
    
    try:
        # Start Celery Beat
        celery_app.start(['beat', '--loglevel=info'])
    except KeyboardInterrupt:
        print("\nStopping Celery Beat...")
        sys.exit(0) 