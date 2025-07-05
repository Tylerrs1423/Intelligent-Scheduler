#!/usr/bin/env python3
"""
Start Simple Celery Worker
Just for testing basic quest generation
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app import celery_app

if __name__ == "__main__":
    print("🚀 Starting Simple Celery Worker...")
    print("📋 This worker will process quest generation tasks")
    print("⏹️  Press Ctrl+C to stop")
    print("-" * 50)
    
    # Start the worker
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--concurrency=1",  # Just one worker process
    ]) 