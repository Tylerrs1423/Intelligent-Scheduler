import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

export type WeekEvent = {
  id: string;
  date: string; // YYYY-MM-DD
  label: string;
  color: string; // Tailwind color class e.g., 'bg-blue-500'
  start: string; // HH:MM in 24h
  end: string;   // HH:MM in 24h
};

function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  d.setDate(d.getDate() + days);
  return d;
}

export function useWeekEvents(weekStart: Date | null) {
  const [events, setEvents] = useState<WeekEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = useCallback(async () => {
    if (!weekStart) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const startStr = toISODate(weekStart);
      const endStr = toISODate(addDays(weekStart, 7));
      
      const response = await api.get('/events/date_range', { 
        params: { start_date: startStr, end_date: endStr } 
      });
      
      const mapped: WeekEvent[] = (response.data || []).map((ev: any) => {
        const s = new Date(ev.start_time);
        const e = new Date(ev.end_time);
        const toHM = (d: Date) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        return {
          id: String(ev.id ?? `${ev.title}-${ev.start_time}`),
          date: toISODate(s),
          label: ev.title || 'Event',
          color: 'bg-sky-500',
          start: toHM(s),
          end: toHM(e),
        } as WeekEvent;
      });
      
      setEvents(mapped);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch events');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [weekStart]);

  // Initial fetch and on week change
  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  // Polling for backend changes
  useEffect(() => {
    const id = setInterval(() => {
      fetchEvents();
    }, 15000);
    return () => clearInterval(id);
  }, [fetchEvents]);

  // Refresh when tab gains focus or becomes visible
  useEffect(() => {
    const onFocus = () => fetchEvents();
    const onVisibility = () => {
      if (document.visibilityState === 'visible') fetchEvents();
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchEvents]);

  return { events, loading, error, refresh: fetchEvents };
}
