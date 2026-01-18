// src/App.js - UPDATED TO HANDLE UPLOAD MODAL
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { WebSocketProvider } from './contexts/WebSocketContext';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import LoginModal from './components/LoginModal';
import VideoUploadModal from './components/VideoUploadModal'; // Import VideoUploadModal
import LandingPage from './pages/LandingPage';
import Home from './pages/Home';
import VehiclesPassing from './pages/VehiclesPassing';
import CongestedRoads from './pages/CongestedRoads';
import Settings from './pages/Settings';
import TrafficPredictions from './pages/TrafficPredictions';
import LocationsList from './pages/LocationsList';
import LocationGroups from './pages/LocationGroups';
import GroupVideos from './pages/GroupVideos';
import './App.css';

// Configure axios defaults once at module level
axios.defaults.baseURL = 'http://127.0.0.1:8000';
axios.defaults.withCredentials = true;

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  
  const [user, setUser] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false); // New state for upload modal
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isAuthChecking, setIsAuthChecking] = useState(true);
  
  // Initialize authentication on mount
  useEffect(() => {
    checkAuthentication();
  }, []);
  
  const checkAuthentication = async () => {
    try {
      // Check localStorage first, then sessionStorage
      const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');
      const storedUser = localStorage.getItem('user') || sessionStorage.getItem('user');
      
      if (token && storedUser) {
        // Set axios header
        axios.defaults.headers.common['Authorization'] = `Token ${token}`;
        
        // Try to parse stored user
        try {
          const parsedUser = JSON.parse(storedUser);
          setUser(parsedUser);
          console.log('✅ User loaded from storage:', parsedUser.username);
        } catch (parseError) {
          console.error('Failed to parse stored user:', parseError);
          clearAuth();
        }
      }
    } catch (error) {
      console.error('❌ Auth check error:', error);
    } finally {
      setIsAuthChecking(false);
    }
  };
  
  const clearAuth = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    sessionStorage.removeItem('auth_token');
    sessionStorage.removeItem('user');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
  };
  
  const isLandingPage = location.pathname === '/';
  
  const handleLoginClick = () => setShowLoginModal(true);
  
  const handleLoginSuccess = (userData) => {
    setUser(userData);
    setShowLoginModal(false);
    
    // Navigate to home if on landing page
    if (location.pathname === '/') {
      navigate('/home');
    }
    
    console.log('✅ Login successful:', userData.username);
  };
  
  const handleLogout = () => {
    clearAuth();
    navigate('/');
    console.log('✅ Logged out');
  };

  const handleUploadClick = () => {
    // Only allow upload if user is logged in
    if (user) {
      setShowUploadModal(true);
    } else {
      // If not logged in, show login modal instead
      setShowLoginModal(true);
    }
  };

  const handleUploadSuccess = (result) => {
    console.log("Upload successful:", result);
    setShowUploadModal(false);
  };

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const closeSidebar = () => {
    setIsSidebarOpen(false);
  };

  // Close sidebar when route changes
  useEffect(() => {
    closeSidebar();
  }, [location.pathname]);

  // Show simple loading while checking auth
  if (isAuthChecking) {
    return (
      <div className="app-container" style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh' 
      }}>
        <div>Loading...</div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {!isLandingPage && (
        <Header 
          user={user}
          onLoginClick={handleLoginClick}
          onLogout={handleLogout}
          toggleSidebar={toggleSidebar}
          onUploadClick={handleUploadClick} // Pass upload handler
        />
      )}
      
      <div className="app-layout">
        {!isLandingPage && (
          <>
            <Sidebar 
              isMobileOpen={isSidebarOpen}
              onClose={closeSidebar}
            />
            {isSidebarOpen && (
              <div 
                className="sidebar-overlay"
                onClick={closeSidebar}
              />
            )}
          </>
        )}
        
        <main className={`main-content ${isLandingPage ? 'no-sidebar' : ''}`}>
          <div className="content-wrapper">
            <Routes>
              <Route path="/" element={
                <LandingPage 
                  onGetStarted={() => user ? navigate('/home') : setShowLoginModal(true)} 
                />
              } />
              <Route path="/home" element={<Home />} />
              <Route path="/overview" element={<Home />} />
              <Route path="/vehicles" element={<VehiclesPassing />} />
              <Route path="/congested" element={<CongestedRoads />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/predictions" element={<TrafficPredictions />} />
              <Route path="/locations" element={<LocationsList />} />
              <Route path="/locations/:locationId/groups" element={<LocationGroups />} />
              <Route path="/locations/:locationId/groups/:groupId" element={<GroupVideos />} />
            </Routes>
          </div>
        </main>
      </div>
      
      {/* Login Modal */}
      <LoginModal
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
        onLoginSuccess={handleLoginSuccess}
      />
      
      {/* Video Upload Modal */}
      <VideoUploadModal
        isOpen={showUploadModal}
        onClose={() => setShowUploadModal(false)}
        onUpload={handleUploadSuccess}
      />
    </div>
  );
}

function App() {
  return (
    <WebSocketProvider>
      <Router>
        <AppContent />
      </Router>
    </WebSocketProvider>
  );
}

export default App;