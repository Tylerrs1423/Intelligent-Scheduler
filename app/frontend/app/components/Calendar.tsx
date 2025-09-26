'use client';

import { useState, useEffect } from 'react';
import { WeekEvent } from '../hooks/useWeekEvents';

interface CalendarProps {
  currentDate: Date;
  weekStart: Date | null;
  events: WeekEvent[];
  loading: boolean;
  error: string | null;
  onEventClick: (event: WeekEvent) => void;
  sleepPreferences: { sleep_start: string; sleep_end: string; has_scheduler?: boolean } | null;
}

export default function Calendar({ 
  currentDate, 
  weekStart, 
  events, 
  loading, 
  error, 
  onEventClick,
  sleepPreferences 
}: CalendarProps) {
  const [now, setNow] = useState<Date | null>(null);
  
  // Set current time on client side only to avoid hydration mismatch
  useEffect(() => {
    setNow(new Date());
  }, []);

  // Update current time frequently
  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 60000); // Update every minute
    return () => clearInterval(interval);
  }, []);

  const HOUR_HEIGHT = 60; // px per hour
  const TOTAL_HOURS = 24;
  const columnHeight = HOUR_HEIGHT * TOTAL_HOURS;

  function timeToOffsetPx(time: string): number {
    const [hStr, mStr] = time.split(':');
    const h = Number(hStr);
    const m = Number(mStr || '0');
    return h * HOUR_HEIGHT + (m / 60) * HOUR_HEIGHT;
  }

  function addDays(date: Date, days: number): Date {
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    d.setDate(d.getDate() + days);
    return d;
  }

  function toISODate(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  if (!weekStart || !now) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <div className="text-gray-500">Loading calendar...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center text-red-500">
          <div className="text-lg font-medium mb-2">Error loading calendar</div>
          <div className="text-sm">{error}</div>
        </div>
      </div>
    );
  }

  const days: Date[] = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  return (
    <div className="flex-1 bg-white overflow-hidden">
      {/* Day headers */}
      <div className="grid grid-cols-7 border-b border-gray-200">
        {dayNames.map((name, index) => {
          const day = days[index];
          const isToday = day.getDate() === now.getDate() && 
                         day.getMonth() === now.getMonth() && 
                         day.getFullYear() === now.getFullYear();
          
          return (
            <div key={name} className="p-4 text-center border-r border-gray-200 last:border-r-0">
              <div className={`text-sm font-medium text-gray-500 mb-1 ${isToday ? 'text-blue-600' : ''}`}>
                {name}
              </div>
              <div className={`text-lg font-semibold ${isToday ? 'text-blue-600' : 'text-gray-900'}`}>
                {day.getDate()}
              </div>
            </div>
          );
        })}
      </div>

      {/* Calendar grid */}
      <div className="flex-1 overflow-auto">
        <div className="grid grid-cols-7 min-h-full">
          {days.map((day) => {
            const iso = toISODate(day);
            const dayEvents = events.filter((e) => e.date === iso);
            const isToday = day.getDate() === now.getDate() && 
                           day.getMonth() === now.getMonth() && 
                           day.getFullYear() === now.getFullYear();
            
            return (
              <div key={iso} className="border-r border-gray-200 last:border-r-0 relative">
                {/* Time slots */}
                <div 
                  className="relative calendar-grid"
                  style={{ height: `${columnHeight}px` }}
                >
                  {/* Hour lines */}
                  {Array.from({ length: 24 }, (_, i) => (
                    <div
                      key={i}
                      className="absolute left-0 right-0 border-t border-gray-100"
                      style={{ top: `${i * HOUR_HEIGHT}px` }}
                    >
                      <div className="absolute -left-12 -top-3 text-xs text-gray-400 font-mono">
                        {i === 0 ? '12 AM' : i < 12 ? `${i} AM` : i === 12 ? '12 PM' : `${i - 12} PM`}
                      </div>
                    </div>
                  ))}

                  {/* Current time indicator */}
                  {isToday && (
                    <div
                      className="absolute left-0 right-0 z-10 time-indicator"
                      style={{ top: `${timeToOffsetPx(`${now.getHours()}:${now.getMinutes()}`)}px` }}
                    >
                    </div>
                  )}

                  {/* Sleep blocks */}
                  {sleepPreferences && sleepPreferences.has_scheduler && (() => {
                    const sleepStart = sleepPreferences.sleep_start;
                    const sleepEnd = sleepPreferences.sleep_end;
                    
                    // Handle sleep that crosses midnight
                    if (sleepStart > sleepEnd) {
                      const top1 = timeToOffsetPx(sleepStart);
                      const height1 = timeToOffsetPx('24:00') - top1;
                      const top2 = 0;
                      const height2 = timeToOffsetPx(sleepEnd);
                      
                      return (
                        <>
                          <div
                            className="absolute left-1 right-1 bg-purple-100 border border-purple-200 rounded opacity-80"
                            style={{ top: `${top1}px`, height: `${height1}px` }}
                          >
                            <div className="px-2 py-1 text-xs text-purple-700 font-medium">
                              💤 Sleep
                            </div>
                          </div>
                          <div
                            className="absolute left-1 right-1 bg-purple-100 border border-purple-200 rounded opacity-80"
                            style={{ top: `${top2}px`, height: `${height2}px` }}
                          >
                            <div className="px-2 py-1 text-xs text-purple-700 font-medium">
                              💤 Sleep
                            </div>
                          </div>
                        </>
                      );
                    } else {
                      const top = timeToOffsetPx(sleepStart);
                      const height = timeToOffsetPx(sleepEnd) - top;
                      
                      return (
                        <div
                          className="absolute left-1 right-1 bg-purple-100 border border-purple-200 rounded opacity-80"
                          style={{ top: `${top}px`, height: `${height}px` }}
                        >
                          <div className="px-2 py-1 text-xs text-purple-700 font-medium">
                            💤 Sleep
                          </div>
                        </div>
                      );
                    }
                  })()}
                  
                  {/* Events */}
                  {dayEvents.map((event, index) => {
                    const top = timeToOffsetPx(event.start);
                    const endTime = timeToOffsetPx(event.end);
                    const height = Math.max(20, endTime - top);
                    
                    // Color mapping based on event priority or index
                    const colorClasses = [
                      'event-blue', 'event-green', 'event-purple', 'event-orange', 
                      'event-red', 'event-pink', 'event-indigo', 'event-teal'
                    ];
                    const colorClass = colorClasses[index % colorClasses.length];
                    
                    return (
                      <div
                        key={event.id}
                        onClick={() => onEventClick(event)}
                        className={`calendar-event absolute left-1 right-1 z-20 ${colorClass}`}
                        style={{ 
                          top: `${top}px`, 
                          height: `${height}px`
                        }}
                      >
                        <div className="px-2 py-1 text-xs font-medium truncate">
                          {event.label}
                        </div>
                        <div className="px-2 pb-1 text-xs opacity-90 truncate">
                          {event.start} - {event.end}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
