'use client';

import { useState } from 'react';

interface SidebarProps {
  onCreateEvent: () => void;
  onSleepSettings: () => void;
  onBufferSettings: () => void;
  onLogout: () => void;
}

export default function Sidebar({ onCreateEvent, onSleepSettings, onBufferSettings, onLogout }: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div className={`bg-white border-r border-gray-200 flex flex-col sidebar-transition ${
      isCollapsed ? 'w-16' : 'w-64'
    }`}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          {!isCollapsed && (
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">AF</span>
              </div>
              <span className="font-semibold text-gray-900">AI Foco</span>
            </div>
          )}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </div>

      {/* Create Event Button */}
      <div className="p-4">
        <button
          onClick={onCreateEvent}
          className="w-full bg-blue-500 hover:bg-blue-600 text-white rounded-lg py-2.5 px-4 font-medium transition-colors flex items-center justify-center space-x-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {!isCollapsed && <span>Create</span>}
        </button>
      </div>

      {/* Week View Indicator */}
      <div className="px-4 pb-4">
        <div className="bg-blue-50 text-blue-700 border border-blue-200 rounded-lg px-3 py-2 text-sm font-medium text-center">
          {!isCollapsed && "Week View"}
        </div>
      </div>

      {/* Navigation Menu */}
      <div className="flex-1 px-4">
        <div className="space-y-1">
          {[
            { label: 'My Calendar', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z', active: true },
            { label: 'Sleep Settings', icon: 'M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z', active: false, onClick: onSleepSettings },
            { label: 'Buffer Settings', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z', active: false, onClick: onBufferSettings }
          ].map(({ label, icon, active, onClick }) => (
            <button
              key={label}
              onClick={onClick}
              className={`w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
              </svg>
              {!isCollapsed && <span>{label}</span>}
            </button>
          ))}
        </div>
      </div>

      {/* User Menu */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">User</p>
              <p className="text-xs text-gray-500 truncate">user@example.com</p>
            </div>
          )}
          <button
            onClick={onLogout}
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            title="Sign out"
          >
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
