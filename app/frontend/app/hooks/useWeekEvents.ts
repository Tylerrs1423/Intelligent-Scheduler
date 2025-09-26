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
      const weekStartStr = toISODate(weekStart);
      const weekEndStr = toISODate(addDays(weekStart, 7));
      
      // Try scheduler slots first, fall back to regular events
      let mapped: WeekEvent[] = [];
      
      try {
        // Get scheduler slots
        const response = await api.get('/events/scheduler-slots');
        const slots = response.data?.slots || [];
        
        // Filter slots to current week and convert to WeekEvent format
        mapped = slots
          .filter((slot: any) => {
            const slotDate = new Date(slot.start_time);
            const slotDateStr = toISODate(slotDate);
            return slotDateStr >= weekStartStr && slotDateStr < weekEndStr;
          })
          .filter((slot: any) => slot.status === 'occupied')
          .map((slot: any) => {
            const s = new Date(slot.start_time);
            const e = new Date(slot.end_time);
            const toHM = (d: Date) => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
            
            // Determine if this is a buffer slot or event slot
            const isBuffer = slot.occupant === 'BUFFER';
            
            return {
              id: String(slot.occupant?.id ?? `${slot.occupant}-${slot.start_time}`),
              date: toISODate(s),
              label: isBuffer ? 'Buffer Time' : (slot.occupant?.title || 'Event'),
              color: isBuffer ? 'bg-gray-400' : 'bg-sky-500',
              start: toHM(s),
              end: toHM(e),
            } as WeekEvent;
          });
      } catch (schedulerError) {
        console.log('Scheduler slots not available, falling back to regular events');
      }
      
      // If no scheduler events, fall back to regular events
      if (mapped.length === 0) {
        const response = await api.get('/events/date_range', { 
          params: { start_date: weekStartStr, end_date: weekEndStr } 
        });
        
        mapped = (response.data || []).map((ev: any) => {
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
      }
      
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
