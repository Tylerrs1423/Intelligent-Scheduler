'use client';

import { useState, useEffect } from 'react';
import { api } from '../api';
import { SleepPreferences } from '../hooks/useSleepPreferences';

interface SleepSettingsModalProps {
  onClose: () => void;
  onSave: () => void;
  currentSleepPreferences?: SleepPreferences | null;
}

export default function SleepSettingsModal({ 
  onClose, 
  onSave, 
  currentSleepPreferences 
}: SleepSettingsModalProps) {
  const [sleepStart, setSleepStart] = useState('');
  const [sleepEnd, setSleepEnd] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Initialize form with current values
  useEffect(() => {
    if (currentSleepPreferences) {
      setSleepStart(currentSleepPreferences.sleep_start || '22:00');
      setSleepEnd(currentSleepPreferences.sleep_end || '08:00');
    } else {
      // Default values
      setSleepStart('22:00');
      setSleepEnd('08:00');
    }
  }, [currentSleepPreferences]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // Convert time format from "HH:MM" to "HH:MM:SS"
      const formatTimeForAPI = (timeStr: string) => {
        if (!timeStr) return timeStr;
        return timeStr.length === 5 ? `${timeStr}:00` : timeStr;
      };

      await api.post('/users/user/sleep-preferences', {
        sleep_start: formatTimeForAPI(sleepStart),
        sleep_end: formatTimeForAPI(sleepEnd)
      });

      onSave();
      onClose();
    } catch (err: any) {
      console.error('Error saving sleep preferences:', err);
      setError(err.response?.data?.detail || 'Failed to save sleep preferences');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Sleep Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSave} className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="sleepStart" className="block text-sm font-medium text-gray-700 mb-2">
                Sleep Start Time
              </label>
              <input
                type="time"
                id="sleepStart"
                value={sleepStart}
                onChange={(e) => setSleepStart(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>

            <div>
              <label htmlFor="sleepEnd" className="block text-sm font-medium text-gray-700 mb-2">
                Sleep End Time
              </label>
              <input
                type="time"
                id="sleepEnd"
                value={sleepEnd}
                onChange={(e) => setSleepEnd(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              />
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-700">
                <strong>Note:</strong> These times define your sleep schedule. The scheduler will avoid scheduling events during these hours.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-500 border border-transparent rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
