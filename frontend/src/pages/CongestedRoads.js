// src/pages/CongestedRoads.js
import React, { useState } from "react";

function CongestedRoads() {
  const [timeFilter, setTimeFilter] = useState("today");

  // Sample congestion data
  const congestionData = [
    {
      road: "Baliwasan Road",
      area: "Baliwasan Area",
      time: "7:30 - 9:00 AM",
      congestionLevel: "High",
      vehiclesPerHour: 2450,
      trend: "increasing"
    },
    {
      road: "San Roque Highway",
      area: "San Roque Area",
      time: "7:45 - 9:15 AM",
      congestionLevel: "High",
      vehiclesPerHour: 1950,
      trend: "stable"
    },
    {
      road: "Zamboanga City Boulevard",
      area: "Downtown Area",
      time: "8:00 - 9:30 AM",
      congestionLevel: "Medium",
      vehiclesPerHour: 1650,
      trend: "decreasing"
    },
    {
      road: "Tumaga Road",
      area: "Tumaga Area",
      time: "4:30 - 6:30 PM",
      congestionLevel: "High",
      vehiclesPerHour: 2150,
      trend: "increasing"
    },
    {
      road: "Gov. Camins Avenue",
      area: "San Jose Area",
      time: "5:00 - 6:30 PM",
      congestionLevel: "Medium",
      vehiclesPerHour: 1800,
      trend: "stable"
    }
  ];

  const getCongestionColor = (level) => {
    switch(level.toLowerCase()) {
      case "high":
        return "text-red-600";
      case "medium":
        return "text-yellow-600";
      case "low":
        return "text-green-600";
      default:
        return "text-gray-600";
    }
  };

  const getTrendIcon = (trend) => {
    switch(trend.toLowerCase()) {
      case "increasing":
        return "↗";
      case "decreasing":
        return "↘";
      case "stable":
        return "→";
      default:
        return "";
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">Traffic Monitor</h1>
        <p className="text-gray-600">Congestion results and peak traffic information</p>
      </header>

      <div className="flex justify-between items-center mb-6">
        <h2 className="section-title">Congested Roads</h2>
        <select 
          className="border rounded p-2 text-sm"
          value={timeFilter}
          onChange={(e) => setTimeFilter(e.target.value)}
        >
          <option value="today">Today</option>
          <option value="week">This Week</option>
          <option value="month">This Month</option>
        </select>
      </div>

      <div className="dashboard-card mb-8">
        <div className="card-header">
          <h3 className="card-title">Peak Hour Traffic</h3>
          <p className="text-sm text-gray-600">Busiest times in monitored areas</p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="area-card">
            <h3 className="area-name">Baliwasan Area</h3>
            <div className="peak-time">
              <span className="peak-label">Morning Peak</span>
              <span className="peak-value">7:30 - 9:00 AM</span>
            </div>
            <p className="text-sm text-gray-600">Average vehicles: 2,450/hr</p>
            
            <div className="peak-time mt-3">
              <span className="peak-label">Evening Peak</span>
              <span className="peak-value">4:30 - 6:30 PM</span>
            </div>
            <p className="text-sm text-gray-600">Average vehicles: 2,150/hr</p>
          </div>
          
          <div className="area-card">
            <h3 className="area-name">San Roque Area</h3>
            <div className="peak-time">
              <span className="peak-label">Morning Peak</span>
              <span className="peak-value">7:45 - 9:15 AM</span>
            </div>
            <p className="text-sm text-gray-600">Average vehicles: 1,950/hr</p>
            
            <div className="peak-time mt-3">
              <span className="peak-label">Evening Peak</span>
              <span className="peak-value">5:00 - 6:30 PM</span>
            </div>
            <p className="text-sm text-gray-600">Average vehicles: 1,800/hr</p>
          </div>
        </div>
      </div>

      <div className="dashboard-card">
        <div className="card-header">
          <h3 className="card-title">Current Road Congestion</h3>
          <p className="text-sm text-gray-600">Live congestion data from traffic cameras</p>
        </div>
        
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Road</th>
                <th>Area</th>
                <th>Peak Time</th>
                <th>Congestion Level</th>
                <th>Vehicles/Hour</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              {congestionData.map((data, index) => (
                <tr key={index}>
                  <td className="font-medium">{data.road}</td>
                  <td>{data.area}</td>
                  <td>{data.time}</td>
                  <td className={`font-bold ${getCongestionColor(data.congestionLevel)}`}>
                    {data.congestionLevel}
                  </td>
                  <td>{data.vehiclesPerHour.toLocaleString()}</td>
                  <td>{getTrendIcon(data.trend)} {data.trend}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default CongestedRoads;