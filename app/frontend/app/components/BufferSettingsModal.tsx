'use client';

import { useState, useEffect } from 'react';
import { api } from '../api';

interface BufferSettingsModalProps {
  onClose: () => void;
  onSave: () => void;
  currentSettings?: {
    defaultBufferBefore: number;
    defaultBufferAfter: number;
    autoBufferEnabled: boolean;
  } | null;
}

export default function BufferSettingsModal({ 
  onClose, 
  onSave, 
  currentSettings 
}: BufferSettingsModalProps) {
  const [defaultBufferBefore, setDefaultBufferBefore] = useState(15);
  const [defaultBufferAfter, setDefaultBufferAfter] = useState(15);
  const [autoBufferEnabled, setAutoBufferEnabled] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Initialize form with current values
  useEffect(() => {
    if (currentSettings) {
      setDefaultBufferBefore(currentSettings.defaultBufferBefore || 15);
      setDefaultBufferAfter(currentSettings.defaultBufferAfter || 15);
      setAutoBufferEnabled(currentSettings.autoBufferEnabled ?? true);
    }
  }, [currentSettings]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      // For now, we'll store buffer preferences in localStorage
      // In the future, this could be stored in the database
      const bufferSettings = {
        defaultBufferBefore,
        defaultBufferAfter,
        autoBufferEnabled
      };
      
      localStorage.setItem('bufferSettings', JSON.stringify(bufferSettings));
      
      // TODO: In the future, save to backend
      // await api.post('/users/user/buffer-preferences', bufferSettings);

      onSave();
      onClose();
    } catch (err: any) {
      console.error('Error saving buffer settings:', err);
      setError('Failed to save buffer settings');
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
          <h2 className="text-xl font-semibold text-gray-900">Buffer Settings</h2>
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
            {/* Auto Buffer Toggle */}
            <div className="flex items-center justify-between">
              <div>
                <label className="text-sm font-medium text-gray-700">
                  Auto Buffer
                </label>
                <p className="text-xs text-gray-500">
                  Automatically add buffer time to new events
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAutoBufferEnabled(!autoBufferEnabled)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  autoBufferEnabled ? 'bg-blue-500' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    autoBufferEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            {/* Default Buffer Before */}
            <div>
              <label htmlFor="bufferBefore" className="block text-sm font-medium text-gray-700 mb-2">
                Default Buffer Before (minutes)
              </label>
              <input
                type="number"
                id="bufferBefore"
                value={defaultBufferBefore}
                onChange={(e) => setDefaultBufferBefore(parseInt(e.target.value) || 0)}
                min="0"
                max="60"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Default Buffer After */}
            <div>
              <label htmlFor="bufferAfter" className="block text-sm font-medium text-gray-700 mb-2">
                Default Buffer After (minutes)
              </label>
              <input
                type="number"
                id="bufferAfter"
                value={defaultBufferAfter}
                onChange={(e) => setDefaultBufferAfter(parseInt(e.target.value) || 0)}
                min="0"
                max="60"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="text-sm text-blue-700">
                <strong>Buffer Time:</strong> Extra time added before and after events to prevent conflicts and allow for transitions between tasks.
              </p>
            </div>

            {/* Buffer Visualization */}
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p className="text-sm font-medium text-gray-700 mb-2">Preview:</p>
              <div className="flex items-center space-x-2 text-xs">
                <div className="bg-gray-300 px-2 py-1 rounded">
                  {defaultBufferBefore}m buffer
                </div>
                <div className="bg-blue-400 text-white px-2 py-1 rounded">
                  Event
                </div>
                <div className="bg-gray-300 px-2 py-1 rounded">
                  {defaultBufferAfter}m buffer
                </div>
              </div>
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
