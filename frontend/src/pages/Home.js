// src/pages/Home.js
import React, { useState, useEffect } from "react";
import axios from "axios";
import { Line } from "react-chartjs-2";
import { 
  Chart as ChartJS, 
  CategoryScale, 
  LinearScale, 
  PointElement, 
  LineElement, 
  BarElement, 
  Title, 
  Tooltip, 
  Legend 
} from "chart.js";

ChartJS.register(
  CategoryScale, 
  LinearScale, 
  PointElement, 
  LineElement, 
  BarElement, 
  Title, 
  Tooltip, 
  Legend
);

function Home() {
  const [overviewData, setOverviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch data from Django API
  useEffect(() => {
    const fetchOverviewData = async () => {
      try {
        const response = await axios.get("http://127.0.0.1:8000/api/analyze/");
        setOverviewData(response.data);
        setLoading(false);
      } catch (err) {
        console.error("API error:", err);
        setError("Failed to load data");
        setLoading(false);
      }
    };

    fetchOverviewData();
  }, []);

  if (loading) return <div className="main-content">Loading...</div>;
  if (error) return <div className="main-content">Error: {error}</div>;
  if (!overviewData) return <div className="main-content">No data available</div>;

  const weeklyData = overviewData.weekly_data || [12500, 11800, 13200, 12700, 14200, 9800, 8500];
  const totalWeeklyVehicles = overviewData.total_vehicles || weeklyData.reduce((sum, value) => sum + value, 0);

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Traffic Monitor
        </h1>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <p style={{ color: '#666', marginRight: '16px' }}>System Operational</p>
          <span style={{
            backgroundColor: '#f0fff4',
            color: '#276749',
            fontSize: '12px',
            fontWeight: '500',
            padding: '2px 10px',
            borderRadius: '4px'
          }}>
            Live
          </span>
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Congested Roads</div>
          <div className="stat-value">{overviewData.congested_roads || 12}</div>
          <div className="stat-change positive-change">
            <span>+2 from yesterday</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Vehicles Passing</div>
          <div className="stat-value">{totalWeeklyVehicles.toLocaleString()}</div>
          <div className="stat-change positive-change">
            <span>+5.2% from last week</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Peak Hour</div>
          <div className="stat-value">{overviewData.peak_hour || '8:00 AM'}</div>
          <div className="stat-change negative-change">
            <span>↑ 1:25 longer than average</span>
          </div>
        </div>
      </div>

      <div className="dashboard-card">
        <div className="card-header">
          <h2 className="card-title">Traffic Overview</h2>
          <select className="select-input" defaultValue="current">
            <option value="current">Current Week</option>
            <option value="previous">Previous Week</option>
          </select>
        </div>
        <p style={{ color: '#666', marginBottom: '16px' }}>Weekly traffic data from camera captures</p>
        
        <div style={{ height: '320px', marginBottom: '24px' }}>
          <Line
            data={{
              labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
              datasets: [
                {
                  label: "Vehicles",
                  data: weeklyData,
                  backgroundColor: "rgba(59, 130, 246, 0.2)",
                  borderColor: "rgba(59, 130, 246, 1)",
                  borderWidth: 2,
                  fill: true,
                  tension: 0.3,
                },
              ],
            }}
            options={{ 
              responsive: true, 
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  display: false
                }
              }
            }}
          />
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '14px', color: '#666' }}>Total weekly vehicles</p>
            <p style={{ fontSize: '20px', fontWeight: 'bold' }}>{totalWeeklyVehicles.toLocaleString()}</p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ fontSize: '14px', color: '#666' }}>Daily Average</p>
            <p style={{ fontSize: '20px', fontWeight: 'bold' }}>{(totalWeeklyVehicles / 7).toLocaleString(undefined, {maximumFractionDigits: 0})}</p>
            <p style={{ fontSize: '14px', color: '#38a169' }}>+5.2% from last week</p>
          </div>
        </div>
      </div>

      <div className="dashboard-card" style={{ marginTop: '24px' }}>
        <div className="card-header">
          <h2 className="card-title">Peak Hour Traffic</h2>
          <p style={{ fontSize: '14px', color: '#666' }}>Busiest times in monitored areas</p>
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          {overviewData.areas && overviewData.areas.map((area, index) => (
            <div key={index} className="area-card">
              <h3 className="area-name">{area.name}</h3>
              <div className="peak-time">
                <span className="peak-label">Morning Peak</span>
                <span className="peak-value">{area.morning_peak}</span>
              </div>
              <p style={{ fontSize: '14px', color: '#666' }}>Average vehicles: {area.morning_volume?.toLocaleString()}/hr</p>
              
              <div className="peak-time" style={{ marginTop: '12px' }}>
                <span className="peak-label">Evening Peak</span>
                <span className="peak-value">{area.evening_peak}</span>
              </div>
              <p style={{ fontSize: '14px', color: '#666' }}>Average vehicles: {area.evening_volume?.toLocaleString()}/hr</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Home;