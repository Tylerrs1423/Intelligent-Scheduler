'use client';

import { useState, useEffect } from 'react';
import { api } from '../api';

interface EventModalProps {
  event: any | null;
  onClose: () => void;
  onSave: () => void;
  currentDate: Date;
}

export default function EventModal({ event, onClose, onSave, currentDate }: EventModalProps) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    start_time: '',
    end_time: '',
    duration: 60,
    time_preference: 'morning',
    priority: 2,
    scheduling_flexibility: 'fixed',
    buffer_before: 0,
    buffer_after: 0
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (event) {
      // Editing existing event
      setFormData({
        title: event.title || '',
        description: event.description || '',
        start_time: event.start_time || '',
        end_time: event.end_time || '',
        duration: event.duration || 60,
        time_preference: event.time_preference || 'morning',
        priority: event.priority || 2,
        scheduling_flexibility: event.scheduling_flexibility || 'fixed',
        buffer_before: event.buffer_before || 0,
        buffer_after: event.buffer_after || 0
      });
    } else {
      // Creating new event - set default times
      const now = new Date();
      const startTime = new Date(now.getTime() + 60 * 60 * 1000); // 1 hour from now
      const endTime = new Date(startTime.getTime() + 60 * 60 * 1000); // 1 hour duration
      
      setFormData(prev => ({
        ...prev,
        start_time: startTime.toISOString().slice(0, 16),
        end_time: endTime.toISOString().slice(0, 16)
      }));
    }
  }, [event]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const eventData = {
        title: formData.title,
        description: formData.description,
        priority: formData.priority,
        scheduling_flexibility: formData.scheduling_flexibility,
        buffer_before: formData.buffer_before,
        buffer_after: formData.buffer_after,
        ...(formData.scheduling_flexibility === 'fixed' ? {
          start_time: formData.start_time,
          end_time: formData.end_time
        } : {
          duration: formData.duration,
          time_preference: formData.time_preference
        })
      };

      if (event) {
        // Update existing event
        await api.put(`/events/update/${event.id}`, eventData);
      } else {
        // Create new event
        await api.post('/events/create', eventData);
      }
      
      onSave();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      if (err.response?.data?.detail) {
        const errorDetail = err.response.data.detail;
        setError(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
      } else {
        setError(event ? 'Failed to update event. Please try again.' : 'Failed to create event. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!event || !window.confirm('Are you sure you want to delete this event?')) {
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      await api.delete(`/events/delete/${event.id}`);
      onSave();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      if (err.response?.data?.detail) {
        const errorDetail = err.response.data.detail;
        setError(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
      } else {
        setError('Failed to delete event. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 modal-backdrop flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">
            {event ? 'Edit Event' : 'Create Event'}
          </h2>
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
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title *
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({...formData, title: e.target.value})}
              required
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Event title"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Event description"
              rows={3}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Scheduling Type
            </label>
            <select
              value={formData.scheduling_flexibility}
              onChange={(e) => setFormData({...formData, scheduling_flexibility: e.target.value})}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="fixed">Fixed (exact time)</option>
              <option value="flexible">Flexible (scheduler finds best time)</option>
            </select>
          </div>

          {formData.scheduling_flexibility === 'fixed' ? (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Start Time *
                </label>
                <input
                  type="datetime-local"
                  value={formData.start_time}
                  onChange={(e) => setFormData({...formData, start_time: e.target.value})}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  End Time *
                </label>
                <input
                  type="datetime-local"
                  value={formData.end_time}
                  onChange={(e) => setFormData({...formData, end_time: e.target.value})}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Duration (minutes)
                </label>
                <input
                  type="number"
                  value={formData.duration}
                  onChange={(e) => setFormData({...formData, duration: parseInt(e.target.value) || 60})}
                  min="1"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Time Preference
                </label>
                <select
                  value={formData.time_preference}
                  onChange={(e) => setFormData({...formData, time_preference: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="morning">Morning (6 AM - 12 PM)</option>
                  <option value="afternoon">Afternoon (12 PM - 6 PM)</option>
                  <option value="evening">Evening (6 PM - 10 PM)</option>
                </select>
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Priority
            </label>
            <select
              value={formData.priority}
              onChange={(e) => setFormData({...formData, priority: parseInt(e.target.value)})}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value={1}>Low</option>
              <option value={2}>Medium</option>
              <option value={3}>High</option>
              <option value={4}>Urgent</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Buffer Before (min)
              </label>
              <input
                type="number"
                value={formData.buffer_before}
                onChange={(e) => setFormData({...formData, buffer_before: parseInt(e.target.value) || 0})}
                min="0"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Buffer After (min)
              </label>
              <input
                type="number"
                value={formData.buffer_after}
                onChange={(e) => setFormData({...formData, buffer_after: parseInt(e.target.value) || 0})}
                min="0"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-between pt-4">
            <div>
              {event && (
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={isLoading}
                  className="px-4 py-2 text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
                >
                  Delete
                </button>
              )}
            </div>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isLoading}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
              >
                {isLoading ? 'Saving...' : (event ? 'Update' : 'Create')}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
