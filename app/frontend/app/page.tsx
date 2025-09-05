'use client';

import { useState, useEffect } from 'react';
import { api, getStoredTokens, setStoredTokens, clearStoredTokens } from './api';
import { useWeekEvents, WeekEvent } from './hooks/useWeekEvents';
import { useSleepPreferences } from './hooks/useSleepPreferences';



function startOfWeekSunday(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const day = d.getDay(); // 0-6, 0 is Sunday
  d.setDate(d.getDate() - day);
  return d;
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

function monthYearForWeek(weekStart: Date): string {
  // Use the middle of the week (Wednesday) to decide displayed month
  const mid = addDays(weekStart, 3);
  return mid.toLocaleString(undefined, { month: 'long', year: 'numeric' });
}

const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function WeekCalendar({ 
  weekStart, 
  events, 
  loading, 
  error,
  onPreviousWeek,
  onNextWeek,
  onToday,
  sleepPreferences,
  schedulerSlots
}: { 
  weekStart: Date | null;
  events: WeekEvent[];
  loading: boolean;
  error: string | null;
  onPreviousWeek: () => void;
  onNextWeek: () => void;
  onToday: () => void;
  sleepPreferences: { sleep_start: string; sleep_end: string; has_scheduler?: boolean } | null;
  schedulerSlots: { start_time: string; end_time: string; occupant: string; status: string }[];
}) {
  const [now, setNow] = useState<Date | null>(null);
  
  // Set current time on client side only to avoid hydration mismatch
  useEffect(() => {
    setNow(new Date());
  }, []);

  const HOUR_HEIGHT = 56; // px per hour
  const TOTAL_HOURS = 24;
  const columnHeight = HOUR_HEIGHT * TOTAL_HOURS;
  const EVENT_HEIGHT_SCALE = 1.6; // 60% larger visual height

  function timeToOffsetPx(time: string): number {
    const [hStr, mStr] = time.split(':');
    const h = Number(hStr);
    const m = Number(mStr || '0');
    return h * HOUR_HEIGHT + (m / 60) * HOUR_HEIGHT;
  }

  // Update current time frequently so the line is reliable
  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 15 * 1000);
    return () => clearInterval(interval);
  }, []); // Empty dependency array - only run once when component mounts

  // Don't render until dates are set to avoid hydration mismatch
  if (!weekStart || !now) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="text-center text-gray-500">Loading calendar...</div>
      </div>
    );
  }

  const days: Date[] = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));

  return (
    <div className="bg-white rounded-lg shadow-sm">
      {/* Header with month and navigation */}
      <div className="p-4 sm:p-6 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            aria-label="Previous week"
            onClick={onPreviousWeek}
            className="h-9 w-9 flex items-center justify-center rounded-full border border-gray-300 text-gray-700 hover:bg-gray-50"
          >
            ←
          </button>
          <button
            aria-label="Today"
            onClick={onToday}
            className="px-3 h-9 flex items-center justify-center rounded-full border border-gray-300 text-gray-700 hover:bg-gray-50"
          >
            Today
          </button>
          <button
            aria-label="Next week"
            onClick={onNextWeek}
            className="h-9 w-9 flex items-center justify-center rounded-full border border-gray-300 text-gray-700 hover:bg-gray-50"
          >
            →
          </button>
        </div>
        <div className="text-lg sm:text-xl font-semibold text-gray-900">
          {monthYearForWeek(weekStart)}
        </div>
        <div className="text-sm text-gray-500">
          {toISODate(weekStart)} – {toISODate(addDays(weekStart, 6))}
        </div>
      </div>

      {/* Grid */}
      <div className="overflow-x-auto">
        <div className="min-w-[640px]">
          {/* Day headers (clean, no grid) */}
          <div className="grid grid-cols-7">
            {dayNames.map((name) => (
              <div key={name} className="px-3 py-3 text-center text-xs sm:text-sm font-medium text-gray-500">
                {name}
              </div>
            ))}
          </div>
          {/* Day cells with Google Calendar-like grid lines */}
          <div className="grid grid-cols-7">
            {days.map((d) => {
              const iso = toISODate(d);
              const dayNumber = d.getDate();
              const dayEvents = events.filter((e) => e.date === iso);
              return (
                <div key={iso} className="border-r border-gray-200 last:border-r-0">
                  {/* Day header - big number in a circle */}
                  <div className="px-2 sm:px-3 pt-1 pb-2 h-14 flex items-center justify-center">
                    {(() => {
                      const isToday =
                        d.getFullYear() === now.getFullYear() &&
                        d.getMonth() === now.getMonth() &&
                        d.getDate() === now.getDate();
                      return (
                        <div
                          className={`inline-flex items-center justify-center flex-shrink-0 text-base font-semibold select-none align-middle 
                            ${isToday ? 'bg-[#1E76E8] text-white ring-4 ring-[#1E76E8]/20 shadow-sm' : 'bg-white text-gray-700'}`}
                          style={{ width: 40, height: 40, borderRadius: 9999, lineHeight: '40px' }}
                        >
                          {dayNumber}
                        </div>
                      );
                    })()}
                  </div>
                  {/* Grid body with horizontal lines */}
                  <div
                    className="bg-white relative border-t border-gray-200 overflow-visible"
                    style={{
                      height: `${columnHeight}px`,
                      backgroundImage:
                        'repeating-linear-gradient(to bottom, rgba(17,24,39,0.06) 0px, rgba(17,24,39,0.06) 1px, transparent 1px, transparent 28px, rgba(17,24,39,0.03) 28px, rgba(17,24,39,0.03) 29px, transparent 29px, transparent 56px)'
                    }}
                  >
                    {/* Current time indicator removed per request */}
                    {/* Sleep blocks - rendered first so events appear on top */}
                    {sleepPreferences && sleepPreferences.has_scheduler && (() => {
                      const sleepStart = sleepPreferences.sleep_start;
                      const sleepEnd = sleepPreferences.sleep_end;
                      
                      // Handle sleep that crosses midnight (e.g., 22:00 to 06:00)
                      if (sleepStart > sleepEnd) {
                        // Sleep starts today and ends tomorrow
                        const top1 = timeToOffsetPx(sleepStart);
                        const height1 = timeToOffsetPx('24:00') - top1;
                        const top2 = 0;
                        const height2 = timeToOffsetPx(sleepEnd);
                        
                        return (
                          <>
                            {/* First part: from sleep start to midnight */}
                            <div
                              className="absolute left-1 right-1 sm:left-2 sm:right-2 bg-purple-200 border-2 border-purple-300 rounded-lg opacity-80"
                              style={{ top: `${top1}px`, height: `${height1}px` }}
                            >
                              <div className="px-2 py-1 text-xs text-purple-800 font-medium">
                                💤 Sleep
                              </div>
                            </div>
                            {/* Second part: from midnight to sleep end */}
                            <div
                              className="absolute left-1 right-1 sm:left-2 sm:right-2 bg-purple-200 border-2 border-purple-300 rounded-lg opacity-80"
                              style={{ top: `${top2}px`, height: `${height2}px` }}
                            >
                              <div className="px-2 py-1 text-xs text-purple-800 font-medium">
                                💤 Sleep
                              </div>
                            </div>
                          </>
                        );
                      } else {
                        // Normal sleep (e.g., 22:00 to 06:00 next day, but displayed as single block)
                        const top = timeToOffsetPx(sleepStart);
                        const height = timeToOffsetPx(sleepEnd) - top;
                        
                        return (
                          <div
                            className="absolute left-1 right-1 sm:left-2 sm:right-2 bg-purple-200 border-2 border-purple-300 rounded-lg opacity-80"
                            style={{ top: `${top}px`, height: `${height}px` }}
                          >
                            <div className="px-2 py-1 text-xs text-purple-800 font-medium">
                              💤 Sleep
                            </div>
                          </div>
                        );
                      }
                    })()}
                    
                    {/* Events absolutely positioned as bubbles */}
                    {dayEvents.map((e) => {
                      const top = timeToOffsetPx(e.start);
                      const rawHeight = timeToOffsetPx(e.end) - timeToOffsetPx(e.start);
                      const height = Math.max(28, rawHeight * EVENT_HEIGHT_SCALE);
                      return (
                        <div
                          key={e.id}
                          className={`absolute left-2 right-2 sm:left-3 sm:right-3 rounded-2xl text-white shadow-md ring-1 ring-black/10 ${e.color}`}
                          style={{ top: `${top}px`, height: `${height}px` }}
                        >
                          <div className="px-3 py-2 sm:py-3 leading-tight text-[13px] sm:text-sm">
                            <div className="text-sm font-semibold">{e.label}</div>
                            <div className="text-[11px] text-white/90">
                              {e.start} - {e.end}
                            </div>
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
    </div>
  );
}

export default function HomePage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddEventModal, setShowAddEventModal] = useState(false);
  const [showSleepPreferencesModal, setShowSleepPreferencesModal] = useState(false);
  const [newEvent, setNewEvent] = useState({
    title: '',
    description: '',
    start_time: '',
    end_time: '',
    duration: 60, // Duration in minutes for flexible events
    time_preference: 'morning', // morning, afternoon, evening
    priority: 2, // 1=LOW, 2=MEDIUM, 3=HIGH, 4=URGENT
    scheduling_flexibility: 'fixed', // fixed or flexible
    buffer_before: 0,
    buffer_after: 0
  });
  const [sleepPreferencesForm, setSleepPreferencesForm] = useState({
    sleep_start: '22:00',
    sleep_end: '06:00'
  });

  // Get current week start for events
  const [weekStart, setWeekStart] = useState<Date | null>(null);
  
  // Set week start on client side
  useEffect(() => {
    setWeekStart(startOfWeekSunday(new Date()));
  }, []);

  // Use the custom hook for events
  const { events, loading, error: eventsError, refresh: refreshEvents } = useWeekEvents(weekStart);
  
  // Use the custom hook for sleep preferences
  const { sleepPreferences, schedulerSlots, loading: sleepLoading, error: sleepError, refresh: refreshSleep } = useSleepPreferences();

  // Week navigation functions
  const goToPreviousWeek = () => {
    if (weekStart) {
      setWeekStart(addDays(weekStart, -7));
    }
  };

  const goToNextWeek = () => {
    if (weekStart) {
      setWeekStart(addDays(weekStart, 7));
    }
  };

  const goToToday = () => {
    setWeekStart(startOfWeekSunday(new Date()));
  };

  // Check for existing tokens on component mount
  useEffect(() => {
    const { accessToken, refreshToken } = getStoredTokens();
    if (accessToken && refreshToken) {
      // Verify token is still valid
      api.get('/users/me')
        .then(() => {
          setIsLoggedIn(true);
        })
        .catch(() => {
          // Token invalid, clear and stay on login
          clearStoredTokens();
        });
    }
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Try to login with username first, then email if that fails
      let response;
      try {
        response = await api.post('/users/login', {
          username: username,
          password: password
        });
      } catch (usernameError: any) {
        // If username login fails, try with email
        if (usernameError.response?.status === 401) {
          response = await api.post('/users/login', {
            username: email, // Use email as username
            password: password
          });
        } else {
          throw usernameError;
        }
      }
      
      const { access_token, refresh_token } = response.data;
      setStoredTokens(access_token, refresh_token);
      setIsLoggedIn(true);
      
    } catch (error: any) {
      if (error.response?.data?.detail) {
        // Convert to string in case it's an object
        const errorDetail = error.response.data.detail;
        setError(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
      } else {
        setError('Login failed. Please check your credentials.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Register new user
      await api.post('/users/register', {
        username: username,
        email: email,
        password: password
      });
      
      // Auto-login after successful registration
      const loginResponse = await api.post('/users/login', {
        username: username,
        password: password
      });
      
      const { access_token, refresh_token } = loginResponse.data;
      setStoredTokens(access_token, refresh_token);
      setIsLoggedIn(true);
      
    } catch (error: any) {
      if (error.response?.data?.detail) {
        // Convert to string in case it's an object
        const errorDetail = error.response.data.detail;
        setError(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
      } else {
        setError('Registration failed. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = () => {
    // For now, just simulate Google sign-in
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    setUsername('');
    setEmail('');
    setPassword('');
    clearStoredTokens();
  };

  const toggleSignUp = () => {
    setIsSignUp(!isSignUp);
    setUsername('');
    setEmail('');
    setPassword('');
    setError('');
  };

  const toggleAddEventModal = () => {
    console.log('Toggling modal from:', showAddEventModal, 'to:', !showAddEventModal);
    setShowAddEventModal(!showAddEventModal);
  };

  const toggleSleepPreferencesModal = () => {
    setShowSleepPreferencesModal(!showSleepPreferencesModal);
  };

  const handleSleepPreferences = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      await api.post('/users/user/sleep-preferences', sleepPreferencesForm);
      setShowSleepPreferencesModal(false);
      setError(''); // Clear any previous errors
      refreshSleep(); // Refresh sleep preferences to show updated data
    } catch (error: any) {
      const errorDetail = error.response?.data?.detail;
      setError(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail || 'Failed to update sleep preferences. Please try again.'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Create event with scheduling configuration
      const eventData = {
        title: newEvent.title,
        description: newEvent.description,
        priority: newEvent.priority,
        scheduling_flexibility: newEvent.scheduling_flexibility,
        buffer_before: newEvent.buffer_before,
        buffer_after: newEvent.buffer_after,
        // Include fields based on scheduling flexibility
        ...(newEvent.scheduling_flexibility === 'fixed' ? {
          start_time: newEvent.start_time,
          end_time: newEvent.end_time
        } : {
          duration: newEvent.duration,
          time_preference: newEvent.time_preference
        })
      };

      await api.post('/events/create', eventData);
      
      // Reset form and close modal
      setNewEvent({
        title: '',
        description: '',
        start_time: '',
        end_time: '',
        duration: 60,
        time_preference: 'morning',
        priority: 2, // 1=LOW, 2=MEDIUM, 3=HIGH, 4=URGENT
        scheduling_flexibility: 'fixed',
        buffer_before: 0,
        buffer_after: 0
      });
      setShowAddEventModal(false);
      
      // Immediately refresh the calendar to show the new event
      refreshEvents();
      
    } catch (error: any) {
      if (error.response?.data?.detail) {
        // Convert to string in case it's an object
        const errorDetail = error.response.data.detail;
        setError(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
      } else {
        setError('Failed to create event. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Calendar page after successful login
  if (isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 p-4">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
            <div className="flex justify-between items-center">
              <h1 className="text-2xl font-bold text-gray-900">Week View</h1>
              <button
                onClick={handleLogout}
                className="bg-red-500 text-white py-2 px-4 rounded-lg text-sm font-medium hover:bg-red-600 transition-colors"
              >
                Sign out
              </button>
            </div>
          </div>

          <WeekCalendar 
            weekStart={weekStart}
            events={events}
            loading={loading}
            error={eventsError}
            onPreviousWeek={goToPreviousWeek}
            onNextWeek={goToNextWeek}
            onToday={goToToday}
            sleepPreferences={sleepPreferences}
            schedulerSlots={schedulerSlots}
          />


          {/* Action Buttons */}
          <div className="mt-6 text-center space-x-4">
            <button 
              onClick={toggleAddEventModal}
              className="bg-blue-500 text-white py-3 px-6 rounded-lg text-lg font-medium hover:bg-blue-600 transition-colors"
            >
              + Add Event
            </button>
            <button 
              onClick={toggleSleepPreferencesModal}
              className="bg-green-500 text-white py-3 px-6 rounded-lg text-lg font-medium hover:bg-green-600 transition-colors"
            >
              🛏️ Sleep Preferences
            </button>
          </div>




          {/* Add Event Modal */}
          {showAddEventModal && (
            <div 
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                zIndex: 99999,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
              onClick={() => setShowAddEventModal(false)}
            >
              <div 
                style={{
                  backgroundColor: 'white',
                  borderRadius: '8px',
                  padding: '24px',
                  width: '100%',
                  maxWidth: '28rem',
                  margin: '0 16px',
                  boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-bold">Add New Event</h2>
                  <button 
                    onClick={() => setShowAddEventModal(false)}
                    className="text-gray-500 hover:text-gray-700 text-2xl"
                  >
                    ×
                  </button>
                </div>
                
                {error && (
                  <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                    {error}
                  </div>
                )}

                <form onSubmit={handleAddEvent} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                    <input
                      type="text"
                      value={newEvent.title}
                      onChange={(e) => setNewEvent({...newEvent, title: e.target.value})}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                      placeholder="Event title"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <textarea
                      value={newEvent.description}
                      onChange={(e) => setNewEvent({...newEvent, description: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                      placeholder="Event description"
                      rows={3}
                    />
                  </div>

                  {/* Show different fields based on scheduling flexibility */}
                  {newEvent.scheduling_flexibility === 'fixed' ? (
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Start Time</label>
                        <input
                          type="datetime-local"
                          value={newEvent.start_time}
                          onChange={(e) => setNewEvent({...newEvent, start_time: e.target.value})}
                          required
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">End Time</label>
                        <input
                          type="datetime-local"
                          value={newEvent.end_time}
                          onChange={(e) => setNewEvent({...newEvent, end_time: e.target.value})}
                          required
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Duration (minutes)</label>
                        <input
                          type="number"
                          value={newEvent.duration}
                          onChange={(e) => setNewEvent({...newEvent, duration: parseInt(e.target.value) || 60})}
                          required
                          min="1"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Time Preference</label>
                        <select
                          value={newEvent.time_preference}
                          onChange={(e) => setNewEvent({...newEvent, time_preference: e.target.value})}
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                        >
                          <option value="morning">Morning (6 AM - 12 PM)</option>
                          <option value="afternoon">Afternoon (12 PM - 6 PM)</option>
                          <option value="evening">Evening (6 PM - 10 PM)</option>
                        </select>
                      </div>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                    <select
                      value={newEvent.priority}
                      onChange={(e) => setNewEvent({...newEvent, priority: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                    >
                      <option value={1}>Low</option>
                      <option value={2}>Medium</option>
                      <option value={3}>High</option>
                      <option value={4}>Urgent</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Scheduling Type</label>
                    <select
                      value={newEvent.scheduling_flexibility}
                      onChange={(e) => setNewEvent({...newEvent, scheduling_flexibility: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                    >
                      <option value="fixed">Fixed (exact time)</option>
                      <option value="flexible">Flexible (scheduler finds best time)</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Buffer Before (min)</label>
                      <input
                        type="number"
                        value={newEvent.buffer_before}
                        onChange={(e) => setNewEvent({...newEvent, buffer_before: parseInt(e.target.value) || 0})}
                        min="0"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Buffer After (min)</label>
                      <input
                        type="number"
                        value={newEvent.buffer_after}
                        onChange={(e) => setNewEvent({...newEvent, buffer_after: parseInt(e.target.value) || 0})}
                        min="0"
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end space-x-3 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowAddEventModal(false)}
                      className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isLoading}
                      className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50"
                    >
                      {isLoading ? 'Creating...' : 'Create Event'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Sleep Preferences Modal */}
          {showSleepPreferencesModal && (
            <div 
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                zIndex: 99999,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
              onClick={() => setShowSleepPreferencesModal(false)}
            >
              <div 
                style={{
                  backgroundColor: 'white',
                  padding: '2rem',
                  borderRadius: '8px',
                  width: '90%',
                  maxWidth: '500px',
                  maxHeight: '90vh',
                  overflow: 'auto'
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <h2 className="text-2xl font-bold text-gray-800 mb-6">Sleep Preferences</h2>
                
                {error && (
                  <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
                    {error}
                  </div>
                )}

                <form onSubmit={handleSleepPreferences} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Sleep Start Time</label>
                    <input
                      type="time"
                      value={sleepPreferencesForm.sleep_start}
                      onChange={(e) => setSleepPreferencesForm({...sleepPreferencesForm, sleep_start: e.target.value})}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-green-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Sleep End Time</label>
                    <input
                      type="time"
                      value={sleepPreferencesForm.sleep_end}
                      onChange={(e) => setSleepPreferencesForm({...sleepPreferencesForm, sleep_end: e.target.value})}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:border-green-500"
                    />
                  </div>

                  <div className="flex space-x-4 pt-4">
                    <button
                      type="submit"
                      disabled={isLoading}
                      className="flex-1 bg-green-500 text-white py-2 px-4 rounded-md hover:bg-green-600 disabled:opacity-50"
                    >
                      {isLoading ? 'Saving...' : 'Save Sleep Preferences'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowSleepPreferencesModal(false)}
                      className="flex-1 bg-gray-500 text-white py-2 px-4 rounded-md hover:bg-gray-600"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Sign In Page
  if (!isSignUp) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-normal text-gray-900 mb-2">Sign in</h1>
            <p className="text-base font-normal text-gray-900">to continue to AI Foco</p>
          </div>
          
          {error && (
            <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
              {error}
            </div>
          )}
          
          <form onSubmit={handleLogin} className="space-y-6">
            <div className="flex justify-center">
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username or email"
                required
                disabled={isLoading}
                className="w-[480px] px-3 py-3 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-base transition-colors disabled:opacity-50"
              />
            </div>
            
            <div className="flex justify-center">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
                disabled={isLoading}
                className="w-[480px] px-3 py-3 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-base transition-colors disabled:opacity-50"
              />
            </div>
            
            <div className="flex justify-center">
              <div className="w-[480px] flex justify-end">
                <span
                  className="text-blue-500 text-sm font-medium hover:text-blue-600 cursor-pointer"
                >
                  Forgot password?
                </span>
              </div>
            </div>
            
            <div className="flex justify-center mt-2">
              <img 
                src="/login.svg" 
                alt="Login" 
                className="w-24 h-auto cursor-pointer hover:opacity-80 transition-opacity"
                onClick={handleLogin}
              />
            </div>
          </form>
          
          <div className="mt-8 text-center">
            <span
              className="text-blue-500 text-sm font-medium hover:text-blue-600 cursor-pointer"
              onClick={toggleSignUp}
            >
              Don't have an account? Sign up here
            </span>
          </div>
          
          <div className="mt-6 flex justify-center">
            <img 
              src="/google.svg" 
              alt="Continue with Google" 
              className="w-24 h-auto cursor-pointer hover:opacity-80 transition-opacity"
              onClick={handleGoogleSignIn}
            />
          </div>
        </div>
      </div>
    );
  }

  // Sign Up Page
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-normal text-gray-900 mb-2">Sign up</h1>
          <p className="text-base font-normal text-gray-900">to create your AI Foco account</p>
        </div>
        
        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSignUp} className="space-y-6">
          <div className="flex justify-center">
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              required
              disabled={isLoading}
              className="w-[480px] px-3 py-3 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-base transition-colors disabled:opacity-50"
            />
          </div>
          
          <div className="flex justify-center">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              required
              disabled={isLoading}
              className="w-[480px] px-3 py-3 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-base transition-colors disabled:opacity-50"
            />
          </div>
          
          <div className="flex justify-center">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
              disabled={isLoading}
              className="w-[480px] px-3 py-3 border border-gray-300 rounded-md focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 text-base transition-colors disabled:opacity-50"
            />
          </div>
          
          <div className="flex justify-center mt-2">
            <img 
              src="/createaccount.svg" 
              alt="Create Account" 
              className="w-24 h-auto cursor-pointer hover:opacity-80 transition-opacity"
              onClick={handleSignUp}
            />
          </div>
        </form>
        
        <div className="mt-8 text-center">
          <span
            className="text-blue-500 text-sm font-medium hover:text-blue-600 cursor-pointer"
            onClick={toggleSignUp}
          >
            Already have an account? Login
          </span>
        </div>
        
        <div className="mt-6 flex justify-center">
          <img 
            src="/google.svg" 
            alt="Continue with Google" 
            className="w-24 h-auto cursor-pointer hover:opacity-80 transition-opacity"
            onClick={handleGoogleSignIn}
          />
        </div>
      </div>
    </div>
  );
}