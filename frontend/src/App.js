// src/App.js
import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Home from "./pages/Home";
import VehiclesPassing from "./pages/VehiclesPassing";
import CongestedRoads from "./pages/CongestedRoads";
import Settings from "./pages/Settings";
import "./App.css";

function App() {
  return (
    <Router>
      <div className="app-container">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/vehicles" element={<VehiclesPassing />} />
            <Route path="/congested" element={<CongestedRoads />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
