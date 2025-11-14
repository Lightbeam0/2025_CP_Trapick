// src/App.js
import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ProgressProvider } from './contexts/ProgressContext';
import Sidebar from './components/Sidebar';
import Home from './pages/Home';
import VehiclesPassing from './pages/VehiclesPassing';
import CongestedRoads from './pages/CongestedRoads';
import Settings from './pages/Settings';
import TrafficPredictions from './pages/TrafficPredictions';
import LocationsList from './pages/LocationsList';
import LocationGroups from './pages/LocationGroups';
import GroupVideos from './pages/GroupVideos';
import './App.css';

function App() {
  return (
    <ProgressProvider>
      <Router>
        <div className="app-container">
          <Sidebar />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/vehicles" element={<VehiclesPassing />} />
            <Route path="/congested" element={<CongestedRoads />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/predictions" element={<TrafficPredictions />} />
            <Route path="/locations" element={<LocationsList />} />
            <Route path="/locations/:locationId/groups" element={<LocationGroups />} />
            <Route path="/locations/:locationId/groups/:groupId" element={<GroupVideos />} />
          </Routes>
        </div>
      </Router>
    </ProgressProvider>
  );
}

export default App;