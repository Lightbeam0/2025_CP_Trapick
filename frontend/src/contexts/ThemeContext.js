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

export const ThemeProvider = ({ children }) => {
  // Check localStorage for saved theme or use system preference
  const getInitialTheme = () => {
    if (typeof window !== 'undefined' && window.localStorage) {
      const storedPref = window.localStorage.getItem('color-theme');
      if (storedPref) {
        return storedPref;
      }

      // Check system preference
      const systemPref = window.matchMedia('(prefers-color-scheme: dark)');
      if (systemPref.matches) {
        return 'dark';
      }
    }
    return 'light'; // Default theme
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
    
    // Update localStorage
    localStorage.setItem('color-theme', newTheme);
    
    // Update theme state
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

  // Listen for system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = (e) => {
      // Only auto-change if user hasn't set a preference
      if (!localStorage.getItem('color-theme')) {
        applyTheme(e.matches ? 'dark' : 'light');
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