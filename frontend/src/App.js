// src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import { WebSocketProvider } from './contexts/WebSocketContext';
import Sidebar from './components/Sidebar';
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

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  
  // Check if we're on the landing page
  const isLandingPage = location.pathname === '/';

  return (
    <div className="app-container">
      {/* Only show sidebar if not on landing page */}
      {!isLandingPage && <Sidebar />}
      
      <div style={{ flex: 1, marginLeft: isLandingPage ? 0 : 0 }}>
        <Routes>
          {/* Landing page route */}
          <Route 
            path="/" 
            element={<LandingPage onGetStarted={() => navigate('/home')} />} 
          />
          
          {/* Dashboard routes */}
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