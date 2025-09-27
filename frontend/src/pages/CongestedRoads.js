// src/pages/CongestedRoads.js
import React, { useState, useEffect } from "react";
import axios from "axios";

function CongestedRoads() {
  const [timeFilter, setTimeFilter] = useState("today");
  const [congestionData, setCongestionData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const defaultCongestionData = [
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
    }
  ];

  useEffect(() => {
    const fetchCongestionData = async () => {
      try {
        const response = await axios.get("http://127.0.0.1:8000/api/congestion/");
        let apiData = response.data;
        
        if (Array.isArray(apiData)) {
          const normalizedData = apiData.map(item => ({
            road: item.road || "Unknown Road",
            area: item.area || "Unknown Area",
            time: item.time || "Unknown Time",
            congestionLevel: item.congestionLevel || "Unknown",
            vehiclesPerHour: item.vehiclesPerHour || 0,
            trend: item.trend || "stable"
          }));
          
          setCongestionData(normalizedData);
        } else {
          setCongestionData(defaultCongestionData);
        }
        
        setLoading(false);
      } catch (err) {
        console.error("API error:", err);
        setError("Failed to load congestion data. Using sample data for demonstration.");
        setCongestionData(defaultCongestionData);
        setLoading(false);
      }
    };

    fetchCongestionData();
  }, []);

  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ fontSize: '18px', color: '#666' }}>Loading congestion data...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Traffic Monitor
        </h1>
        <p style={{ color: '#666', margin: 0 }}>Congestion results and peak traffic information</p>
      </header>

      {error && (
        <div style={{ 
          backgroundColor: '#fff3cd', 
          border: '1px solid #ffeaa7', 
          color: '#856404',
          padding: '12px 16px',
          borderRadius: '4px',
          marginBottom: '24px'
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 style={{ fontSize: '24px', fontWeight: '600', color: '#2d3748', margin: 0 }}>
          Congested Roads
        </h2>
        <select 
          className="select-input"
          value={timeFilter}
          onChange={(e) => setTimeFilter(e.target.value)}
        >
          <option value="today">Today</option>
          <option value="week">This Week</option>
          <option value="month">This Month</option>
        </select>
      </div>

      <div className="dashboard-card">
        <div className="card-header">
          <h3 className="card-title">Current Road Congestion</h3>
          <p style={{ fontSize: '14px', color: '#666' }}>Live congestion data from traffic cameras</p>
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
                  <td style={{ fontWeight: '600' }}>{data.road}</td>
                  <td>{data.area}</td>
                  <td>{data.time}</td>
                  <td>
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '4px 12px',
                      borderRadius: '16px',
                      fontSize: '12px',
                      fontWeight: '600',
                      backgroundColor: 
                        data.congestionLevel === 'High' ? '#fee2e2' : 
                        data.congestionLevel === 'Medium' ? '#fef3c7' : '#d1fae5',
                      color: 
                        data.congestionLevel === 'High' ? '#dc2626' : 
                        data.congestionLevel === 'Medium' ? '#d97706' : '#065f46'
                    }}>
                      {data.congestionLevel}
                    </span>
                  </td>
                  <td style={{ fontWeight: '600' }}>{(data.vehiclesPerHour || 0).toLocaleString()}</td>
                  <td>
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '14px',
                      color: 
                        data.trend === 'increasing' ? '#dc2626' : 
                        data.trend === 'decreasing' ? '#16a34a' : '#2563eb'
                    }}>
                      {data.trend === 'increasing' ? '↗' : data.trend === 'decreasing' ? '↘' : '→'}
                      {data.trend}
                    </span>
                  </td>
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