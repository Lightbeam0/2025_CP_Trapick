// src/contexts/ThemeContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';

const ThemeContext = createContext();

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children, defaultTheme = 'light' }) => {
  // Determine initial theme
  const getInitialTheme = () => {
    if (typeof window !== 'undefined' && window.localStorage) {
      const storedPref = window.localStorage.getItem('color-theme');
      if (storedPref) {
        // If user has previously toggled, respect their choice
        return storedPref;
      }
    }
    // DEFAULT TO LIGHT: Ignore system preference if no stored choice exists
    return defaultTheme; 
  };

  const [theme, setTheme] = useState(getInitialTheme);
  const [isInitialized, setIsInitialized] = useState(false);

  // Apply theme class to document
  const applyTheme = (newTheme) => {
    const root = window.document.documentElement;
    
    // Remove previous theme classes
    root.classList.remove('light', 'dark');
    
    // Add new theme class
    root.classList.add(newTheme);
    
    // Update localStorage so the choice persists on refresh
    localStorage.setItem('color-theme', newTheme);
    
    // Update state
    setTheme(newTheme);
  };

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    applyTheme(newTheme);
  };

  // Initialize theme on mount
  useEffect(() => {
    if (!isInitialized) {
      applyTheme(theme);
      setIsInitialized(true);
    }
  }, [theme, isInitialized]);

  // Optional: Listen for system changes ONLY if user hasn't made a choice yet.
  // Since we want a strict Light default, we generally disable auto-switching 
  // once the app loads to prevent unexpected jumps to Dark mode.
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = (e) => {
      // Only react if the user has NEVER set a preference manually
      if (!localStorage.getItem('color-theme')) {
        // We intentionally do NOT auto-update here to maintain the "Light Default" requirement.
        // If you wanted it to follow system on first load ONLY, you could call applyTheme here.
        // But for a strict Light default, we do nothing.
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const value = {
    theme,
    toggleTheme,
    isDark: theme === 'dark',
    isLight: theme === 'light'
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};