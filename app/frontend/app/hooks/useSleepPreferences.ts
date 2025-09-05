import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

export type SleepPreferences = {
  sleep_start: string;
  sleep_end: string;
  has_scheduler: boolean;
};

export type SchedulerSlot = {
  start_time: string;
  end_time: string;
  occupant: string;
  status: 'AVAILABLE' | 'SLEEP' | 'OCCUPIED';
};

export function useSleepPreferences() {
  const [sleepPreferences, setSleepPreferences] = useState<SleepPreferences | null>(null);
  const [schedulerSlots, setSchedulerSlots] = useState<SchedulerSlot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSleepPreferences = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      console.log('Fetching sleep preferences...');
      const response = await api.get('/users/user/sleep-preferences');
      const data = response.data;
      console.log('Sleep preferences response:', data);
      
      // Convert time format from "HH:MM:SS" to "HH:MM"
      const formatTime = (timeStr: string) => {
        if (!timeStr) return timeStr;
        return timeStr.substring(0, 5); // Take only HH:MM part
      };
      
      const formattedData = {
        sleep_start: formatTime(data.sleep_start),
        sleep_end: formatTime(data.sleep_end),
        has_scheduler: data.has_scheduler || false
      };
      
      console.log('Formatted sleep preferences:', formattedData);
      setSleepPreferences(formattedData);
    } catch (err: any) {
      console.error('Error fetching sleep preferences:', err);
      setError(err.message || 'Failed to fetch sleep preferences');
      setSleepPreferences(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchSchedulerSlots = useCallback(async () => {
    if (!sleepPreferences?.has_scheduler) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.get('/users/user/scheduler/slots');
      setSchedulerSlots(response.data.slots || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch scheduler slots');
      setSchedulerSlots([]);
    } finally {
      setLoading(false);
    }
  }, [sleepPreferences?.has_scheduler]);

  // Fetch sleep preferences on mount
  useEffect(() => {
    fetchSleepPreferences();
  }, [fetchSleepPreferences]);

  // Fetch scheduler slots when sleep preferences are available
  useEffect(() => {
    if (sleepPreferences?.has_scheduler) {
      fetchSchedulerSlots();
    }
  }, [sleepPreferences?.has_scheduler, fetchSchedulerSlots]);

  return { 
    sleepPreferences, 
    schedulerSlots, 
    loading, 
    error, 
    refresh: fetchSleepPreferences,
    refreshSlots: fetchSchedulerSlots
  };
}
