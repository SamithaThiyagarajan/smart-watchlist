import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';

const Navbar = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const initial = (user?.email || 'U').charAt(0).toUpperCase();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isDark = theme === 'dark';

  return (
    <nav className={`sticky top-0 z-50 border-b ${isDark ? 'bg-[#0d0d1a] border-[#2a2a45]' : 'bg-white border-[#e6eaf0]'}`}>
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="flex justify-between items-center h-14">
          <div className="flex items-center gap-8">
            <a href="#top" className="flex items-center gap-2.5">
              <span className="w-7 h-7 rounded brand-gradient flex items-center justify-center text-white text-[11px] font-semibold tracking-tight">
                SW
              </span>
              <span className={`text-[15px] font-semibold tracking-tight ${isDark ? 'text-white' : 'text-[#2d3436]'}`}>
                Smart Watchlist
              </span>
            </a>
            <div className="hidden md:flex items-center gap-6">
              <a href="#digest" className={`text-[13px] font-medium ${isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#2d3436]'}`}>
                Digest
              </a>
              <a href="#watchlist" className={`text-[13px] font-medium ${isDark ? 'text-gray-400 hover:text-white' : 'text-[#636e72] hover:text-[#2d3436]'}`}>
                Watchlist
              </a>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-3">
            {/* Theme Toggle - Simple Light/Dark Switch */}
            <button
              onClick={toggleTheme}
              className={`w-10 h-6 rounded-full flex items-center transition-colors duration-200 ${
                isDark ? 'bg-[#667eea]' : 'bg-gray-300'
              }`}
            >
              <span
                className={`w-4 h-4 bg-white rounded-full shadow-sm transform transition-transform duration-200 ${
                  isDark ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
            <span className={`text-[11px] font-medium ${isDark ? 'text-gray-400' : 'text-[#636e72]'}`}>
              {isDark ? 'Dark' : 'Light'}
            </span>

            <div className="flex items-center gap-2 pl-2 border-l border-line">
              <span className="w-7 h-7 rounded-full brand-gradient text-white text-[11px] font-semibold flex items-center justify-center">
                {initial}
              </span>
              <span className={`text-[12px] ${isDark ? 'text-gray-400' : 'text-[#636e72]'} max-w-[160px] truncate`}>
                {user?.email}
              </span>
            </div>
            <button
              onClick={handleLogout}
              className={`h-8 px-3 text-[12px] font-medium ${isDark ? 'text-gray-400 hover:text-white border-[#2a2a45]' : 'text-[#636e72] hover:text-[#2d3436] border-[#e6eaf0]'} border rounded hover:bg-card-muted`}
            >
              Logout
            </button>
          </div>

          <div className="md:hidden flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className={`w-10 h-6 rounded-full flex items-center transition-colors duration-200 ${
                isDark ? 'bg-[#667eea]' : 'bg-gray-300'
              }`}
            >
              <span
                className={`w-4 h-4 bg-white rounded-full shadow-sm transform transition-transform duration-200 ${
                  isDark ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
            <button
              onClick={() => setIsOpen(!isOpen)}
              className={`p-2 rounded ${isDark ? 'text-white hover:bg-[#1a1a2e]' : 'text-[#2d3436] hover:bg-[#f8f9fb]'}`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {isOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {isOpen && (
          <div className={`md:hidden py-3 border-t ${isDark ? 'border-[#2a2a45]' : 'border-[#e6eaf0]'}`}>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 px-1 py-1">
                <span className="w-7 h-7 rounded-full brand-gradient text-white text-[11px] font-semibold flex items-center justify-center">
                  {initial}
                </span>
                <span className={`text-[13px] ${isDark ? 'text-gray-400' : 'text-[#636e72]'} truncate`}>{user?.email}</span>
              </div>
              <a href="#digest" className={`text-[13px] font-medium ${isDark ? 'text-white' : 'text-[#2d3436]'} px-1 py-2`}>Digest</a>
              <a href="#watchlist" className={`text-[13px] font-medium ${isDark ? 'text-white' : 'text-[#2d3436]'} px-1 py-2`}>Watchlist</a>
              <button
                onClick={handleLogout}
                className="h-9 px-3 text-[13px] font-medium text-white btn-brand rounded"
              >
                Logout
              </button>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;