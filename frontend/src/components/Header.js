// src/components/Header.js - ADD SYNC BUTTON
import React, { useState } from 'react';
import { FaUserCircle, FaSignOutAlt, FaCog, FaHome, FaChevronDown, FaBars, FaTimes, FaUpload, FaCloudUploadAlt, FaSync } from 'react-icons/fa';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';

const Header = ({ user, onLoginClick, onLogout, toggleSidebar, onUploadClick }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);

  // 🔒 Detect cloud deployment and check if user is admin
  const isCloudDeployment = process.env.NODE_ENV === 'production';
  const isAdmin = user && (user.is_staff || user.is_superuser);
  
  // 🔒 Show sync button ONLY in local (development) mode for admin users
  const showSyncButton = !isCloudDeployment && isAdmin;

  const handleUserMenuToggle = () => {
    setShowUserMenu(!showUserMenu);
  };

  const handleNavigation = (path) => {
    navigate(path);
    setShowUserMenu(false);
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

  // 🔄 Handle sync to cloud
  const handleSyncToCloud = async () => {
    if (isSyncing) return;
    
    const confirmed = window.confirm(
      '🌐 Sync Data to Cloud?\n\n' +
      'This will:\n' +
      '• Check what data is available locally\n' +
      '• Send all processed analyses to cloud\n' +
      '• Preserve cloud dashboard data\n\n' +
      'Continue?'
    );
    
    if (!confirmed) return;

    setIsSyncing(true);
    setSyncStatus({ type: 'info', message: 'Checking sync status...' });

    try {
      const statusResponse = await axios.get('/api/sync/status/');
      
      console.log('📊 Sync Status:', statusResponse.data);
      
      const { locations, videos, analyses } = statusResponse.data;
      
      if (analyses === 0) {
        setSyncStatus({ 
          type: 'warning', 
          message: 'No data to sync. Process some videos first.' 
        });
        setIsSyncing(false);
        setTimeout(() => setSyncStatus(null), 5000);
        return;
      }

      const finalConfirm = window.confirm(
        `📊 Ready to Sync:\n\n` +
        `• ${locations} Location(s)\n` +
        `• ${videos} Completed Video(s)\n` +
        `• ${analyses} Analysis/Analyses\n\n` +
        `Proceed with sync?`
      );

      if (!finalConfirm) {
        setIsSyncing(false);
        setSyncStatus(null);
        return;
      }

      setSyncStatus({ type: 'info', message: 'Syncing data to cloud...' });
      
      const syncResponse = await axios.post('/api/sync/execute/');
      
      console.log('✅ Sync Response:', syncResponse.data);

      if (syncResponse.data.success) {
        setSyncStatus({ 
          type: 'success', 
          message: `✅ Sync Complete! ${syncResponse.data.results.analyses} analyses synced.` 
        });
        
        setTimeout(() => {
          alert(
            '🎉 Sync Successful!\n\n' +
            `• Locations: ${syncResponse.data.results.locations}\n` +
            `• Videos: ${syncResponse.data.results.videos}\n` +
            `• Analyses: ${syncResponse.data.results.analyses}\n\n` +
            'Check your cloud dashboard to view the data.'
          );
        }, 500);
      } else {
        setSyncStatus({ 
          type: 'error', 
          message: `❌ Sync Failed: ${syncResponse.data.message}` 
        });
      }

    } catch (error) {
      console.error('❌ Sync Error:', error);
      
      let errorMessage = 'Sync failed. ';
      
      if (error.response) {
        errorMessage += error.response.data?.error || error.response.statusText;
      } else if (error.request) {
        errorMessage += 'No response from server. Check your connection.';
      } else {
        errorMessage += error.message;
      }
      
      setSyncStatus({ type: 'error', message: `❌ ${errorMessage}` });
    } finally {
      setIsSyncing(false);
      setTimeout(() => setSyncStatus(null), 5000);
    }
  };

  return (
    <header className="header">
      {/* Left Section */}
      <div className="header-left">
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
        {/* Sync to Cloud Button - ONLY for admin in LOCAL mode */}
        {showSyncButton && (
          <button
            onClick={handleSyncToCloud}
            className={`sync-button-header ${isSyncing ? 'syncing' : ''}`}
            title="Sync Data to Cloud"
            aria-label="Sync Data to Cloud"
            disabled={isSyncing}
          >
            {isSyncing ? (
              <>
                <FaSync className="spin" size={18} />
                <span className="sync-text">Syncing...</span>
              </>
            ) : (
              <>
                <FaCloudUploadAlt size={18} />
                <span className="sync-text">Sync to Cloud</span>
              </>
            )}
          </button>
        )}

        {/* Upload Video Button - ONLY in LOCAL (development) mode */}
        {user && onUploadClick && !isCloudDeployment && (
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
                  <span className="user-role">{user.role || (isAdmin ? 'Admin' : 'User')}</span>
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
                        {user.role || (isAdmin ? 'Administrator' : 'User')}
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
            // Sign In button — hidden in cloud deployment
            !isCloudDeployment && (
              <button
                onClick={onLoginClick}
                className="login-button"
              >
                <FaUserCircle size={16} className="login-icon" />
                Sign In
              </button>
            )
          )}
        </div>
      </div>

      {/* Sync Status Notification */}
      {syncStatus && (
        <div className={`sync-notification ${syncStatus.type}`}>
          {syncStatus.message}
        </div>
      )}
    </header>
  );
};

export default Header;