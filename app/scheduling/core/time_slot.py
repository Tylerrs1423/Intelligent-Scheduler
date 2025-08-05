"""
Time slot representation for the scheduling system.
"""

from datetime import datetime, timedelta
from typing import Any
from .constants import BUFFER, AVAILABLE, RESERVED


class CleanTimeSlot:
    """
    A cleaner TimeSlot system where each slot represents exactly one thing:
    - A task (with occupant=Quest object)
    - A buffer zone (with occupant=BUFFER)
    - Available time (with occupant=AVAILABLE)
    """
    def __init__(self, start: datetime, end: datetime, occupant: Any = AVAILABLE, is_flexible: bool = False):
        self.start = start
        self.end = end
        self.occupant = occupant
        self.is_flexible = is_flexible

    def duration(self) -> timedelta:
        return self.end - self.start

    def __lt__(self, other):
        return self.start < other.start

    def __repr__(self):
        if self.occupant == BUFFER:
            return f"BufferSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')})"
        elif self.occupant == AVAILABLE:
            return f"AvailableSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')})"
        elif self.occupant:
            occupant_name = getattr(self.occupant, 'title', str(self.occupant))
            return f"TaskSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')}, {occupant_name})"
        else:
            return f"AvailableSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')})" 