// src/components/Header.js - UPDATED WITH UPLOAD BUTTON
import React, { useState } from 'react';
import { FaUserCircle, FaSignOutAlt, FaCog, FaHome, FaChevronDown, FaBars, FaTimes, FaUpload } from 'react-icons/fa';
import { useNavigate, useLocation } from 'react-router-dom';

const Header = ({ user, onLoginClick, onLogout, toggleSidebar, onUploadClick }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleUserMenuToggle = () => {
    setShowUserMenu(!showUserMenu);
  };

  const handleNavigation = (path) => {
    navigate(path);
    setShowUserMenu(false);
    // Close sidebar on mobile when navigating
    if (window.innerWidth <= 768) {
      setIsMobileMenuOpen(false);
    }
  };

  const getPageTitle = () => {
    const path = location.pathname;
    const titles = {
      '/home': 'Dashboard Overview',
      '/overview': 'Dashboard Overview',
      '/vehicles': 'Vehicles Passing Analysis',
      '/congested': 'Congested Roads Analysis',
      '/locations': 'Location Management',
      '/predictions': 'Traffic Predictions',
      '/settings': 'System Settings',
    };
    return titles[path] || 'Traffic Monitoring Dashboard';
  };

  const handleMobileMenuToggle = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
    if (toggleSidebar) {
      toggleSidebar();
    }
  };

  return (
    <header className="header">
      {/* Left Section */}
      <div className="header-left">
        {/* Mobile Menu Button - Only visible on mobile */}
        <button
          className="mobile-menu-button"
          onClick={handleMobileMenuToggle}
          aria-label="Toggle menu"
        >
          {isMobileMenuOpen ? <FaTimes size={20} /> : <FaBars size={20} />}
        </button>
        
        <div className="logo-section">
          <div className="logo" onClick={() => handleNavigation('/home')}>
            <span className="logo-icon">🚦</span>
            <span className="logo-text">TRAPICK</span>
          </div>
        </div>
        
        <h1 className="page-title">{getPageTitle()}</h1>
      </div>

      {/* Right Section */}
      <div className="header-right">
        {/* Upload Video Button - Only show when logged in */}
        {user && onUploadClick && (
        <button
            onClick={onUploadClick}
            className="upload-button-header-alt"
            title="Upload Video"
            aria-label="Upload Video"
        >
            <FaUpload size={18} />
        </button>
        )}

        {/* Home Button */}
        <button
          onClick={() => handleNavigation('/home')}
          className="icon-button"
          title="Go to Dashboard"
        >
          <FaHome size={20} />
        </button>

        {/* User Profile */}
        <div className="user-container">
          {user ? (
            <>
              <button
                onClick={handleUserMenuToggle}
                className="user-button"
              >
                <div className="user-avatar">
                  <FaUserCircle size={32} />
                </div>
                <div className="user-info">
                  <span className="user-name">{user.name || user.username}</span>
                  <span className="user-role">{user.role || 'Admin'}</span>
                </div>
                <FaChevronDown 
                  size={12} 
                  className={`chevron-icon ${showUserMenu ? 'rotated' : ''}`}
                />
              </button>

              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-dropdown-header">
                    <div className="dropdown-avatar">
                      <FaUserCircle size={48} />
                    </div>
                    <div className="user-dropdown-info">
                      <strong>{user.name || user.username}</strong>
                      <span>{user.email || 'admin@trapick.com'}</span>
                      <small className="user-role-badge">
                        {user.role || 'Administrator'}
                      </small>
                    </div>
                  </div>
                  
                  <div className="user-dropdown-menu">
                    <button
                      onClick={() => handleNavigation('/profile')}
                      className="dropdown-item"
                    >
                      <FaUserCircle className="dropdown-icon" />
                      My Profile
                    </button>
                    
                    <button
                      onClick={() => handleNavigation('/settings')}
                      className="dropdown-item"
                    >
                      <FaCog className="dropdown-icon" />
                      Settings
                    </button>
                    
                    <div className="dropdown-divider"></div>
                    
                    <button
                      onClick={onLogout}
                      className="dropdown-item logout-item"
                    >
                      <FaSignOutAlt className="dropdown-icon" />
                      Sign Out
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <button
              onClick={onLoginClick}
              className="login-button"
            >
              <FaUserCircle size={16} className="login-icon" />
              Sign In
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;