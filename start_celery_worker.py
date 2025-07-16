#!/usr/bin/env python3
"""
Start Celery Worker for AI Foco
"""

import os
import sys
from app.celery_app import celery_app

if __name__ == "__main__":
    print("Starting Celery Worker for AI Foco...")
    print("This will process scheduled daily quest tasks")
    print("Press Ctrl+C to stop")
    
    try:
        # Start Celery Worker
        celery_app.start(['worker', '--loglevel=info'])
    except KeyboardInterrupt:
        print("\nStopping Celery Worker...")
        sys.exit(0) 