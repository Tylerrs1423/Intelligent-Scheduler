'use client';

import { useState, useEffect } from 'react';
import { api, getStoredTokens, setStoredTokens, clearStoredTokens } from './api';
import { useWeekEvents } from './hooks/useWeekEvents';
import { useSleepPreferences } from './hooks/useSleepPreferences';
import { Calendar, Sidebar, Header, EventModal, LoginForm, SleepSettingsModal, BufferSettingsModal } from './components';



// Utility functions
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

export default function HomePage() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showEventModal, setShowEventModal] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<any>(null);
  const [showSleepModal, setShowSleepModal] = useState(false);
  const [showBufferModal, setShowBufferModal] = useState(false);
  const [currentDate, setCurrentDate] = useState(new Date());

  // Get current week start for events
  const [weekStart, setWeekStart] = useState<Date | null>(null);
  
  // Set week start on client side - start from today onwards
  useEffect(() => {
    setWeekStart(startOfWeekSunday(new Date()));
  }, []);

  // Use the custom hook for events
  const { events, loading, error: eventsError, refresh: refreshEvents } = useWeekEvents(weekStart);
  
  // Use the custom hook for sleep preferences
  const { sleepPreferences, schedulerSlots, loading: sleepLoading, error: sleepError, refresh: refreshSleep } = useSleepPreferences();

  // Navigation functions
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
    const today = new Date();
    setCurrentDate(today);
    setWeekStart(startOfWeekSunday(today));
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
      } catch (usernameError: unknown) {
        // If username login fails, try with email
        if ((usernameError as { response?: { status?: number } }).response?.status === 401) {
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
      
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      if (err.response?.data?.detail) {
        // Convert to string in case it's an object
        const errorDetail = err.response.data.detail;
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
      
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      if (err.response?.data?.detail) {
        // Convert to string in case it's an object
        const errorDetail = err.response.data.detail;
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

  const handleCreateEvent = () => {
    setSelectedEvent(null);
    setShowEventModal(true);
  };

  const handleEditEvent = (event: any) => {
    setSelectedEvent(event);
    setShowEventModal(true);
  };

  const handleEventSaved = () => {
    setShowEventModal(false);
    setSelectedEvent(null);
    refreshEvents();
  };

  const handleSleepSettings = () => {
    setShowSleepModal(true);
  };

  const handleSleepSettingsSaved = () => {
    setShowSleepModal(false);
    refreshSleep(); // Refresh sleep preferences data
  };

  const handleBufferSettings = () => {
    setShowBufferModal(true);
  };

  const handleBufferSettingsSaved = () => {
    setShowBufferModal(false);
    // Refresh events to show any buffer changes
    refreshEvents();
  };

  // Calendar page after successful login
  if (isLoggedIn) {
    return (
      <div className="min-h-screen bg-white flex">
        {/* Sidebar */}
        <Sidebar 
          onCreateEvent={handleCreateEvent}
          onSleepSettings={handleSleepSettings}
          onBufferSettings={handleBufferSettings}
          onLogout={handleLogout}
        />
        
        {/* Main Content */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <Header 
            currentDate={currentDate}
            onPreviousWeek={goToPreviousWeek}
            onNextWeek={goToNextWeek}
            onToday={goToToday}
            onCreateEvent={handleCreateEvent}
          />
          
          {/* Calendar */}
          <div className="flex-1 overflow-hidden">
            <Calendar
              currentDate={currentDate}
              weekStart={weekStart}
              events={events}
              loading={loading}
              error={eventsError}
              onEventClick={handleEditEvent}
              sleepPreferences={sleepPreferences}
            />
          </div>
        </div>

        {/* Event Modal */}
        {showEventModal && (
          <EventModal
            event={selectedEvent}
            onClose={() => setShowEventModal(false)}
            onSave={handleEventSaved}
            currentDate={currentDate}
          />
        )}

        {/* Sleep Settings Modal */}
        {showSleepModal && (
          <SleepSettingsModal
            onClose={() => setShowSleepModal(false)}
            onSave={handleSleepSettingsSaved}
            currentSleepPreferences={sleepPreferences}
          />
        )}

        {/* Buffer Settings Modal */}
        {showBufferModal && (
          <BufferSettingsModal
            onClose={() => setShowBufferModal(false)}
            onSave={handleBufferSettingsSaved}
            currentSettings={null} // TODO: Load from localStorage or backend
          />
        )}
      </div>
    );
  }

  // Login/Signup Page
  return (
    <LoginForm
      isSignUp={isSignUp}
      username={username}
      email={email}
      password={password}
      isLoading={isLoading}
      error={error}
      onUsernameChange={setUsername}
      onEmailChange={setEmail}
      onPasswordChange={setPassword}
      onLogin={handleLogin}
      onSignUp={handleSignUp}
      onGoogleSignIn={handleGoogleSignIn}
      onToggleSignUp={toggleSignUp}
    />
  );
}