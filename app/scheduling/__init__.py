"""
AI Foco Scheduling System

A modular scheduling system with advanced algorithms for intelligent task placement.
Designed to work independently but easily integratable with APIs later.
"""

from .core.scheduler import CleanScheduler
from .core.time_slot import CleanTimeSlot
from .core.constants import BUFFER, AVAILABLE, RESERVED

# Version for future API compatibility
__version__ = "1.0.0" 