import React from 'react';
import { useTheme } from '../context/ThemeContext';

const themeLabel = {
  light: 'Light',
  dark: 'Dark',
  pnl: 'Pulse',
};

const ThemeToggle = () => {
  const { theme, cycleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={cycleTheme}
      className="h-8 px-2.5 rounded border border-line text-[12px] font-medium text-muted hover:text-ink hover:border-accent/40 bg-card"
      title="Cycle Light, Dark, and Pulse (activity tint)"
    >
      {themeLabel[theme] || 'Light'}
    </button>
  );
};

export default ThemeToggle;
