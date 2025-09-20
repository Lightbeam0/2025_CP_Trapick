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
  const [weeklyData, setWeeklyData] = useState([]);

  // Fetch weekly data from Django API
  useEffect(() => {
    axios.get("/api/analyze/")
      .then((res) => {
        // Example weekly aggregation (placeholder for now)
        setWeeklyData([12500, 11800, 13200, 12700, 14200, 9800, 8500]);
      })
      .catch((err) => {
        console.error("API error:", err);
        // Fallback data for demo purposes
        setWeeklyData([12500, 11800, 13200, 12700, 14200, 9800, 8500]);
      });
  }, []);

  // Calculate total weekly vehicles
  const totalWeeklyVehicles = weeklyData.reduce((sum, value) => sum + value, 0);

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">Traffic Monitor</h1>
        <div className="flex items-center mt-2">
          <p className="text-gray-600 mr-4">System Operational</p>
          <span className="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded">
            Live
          </span>
        </div>
      </header>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Congested Roads</div>
          <div className="stat-value">12</div>
          <div className="stat-change positive-change">
            <span>+2 from yesterday</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Vehicles Passing</div>
          <div className="stat-value">54,200</div>
          <div className="stat-change positive-change">
            <span>+5.2% from last week</span>
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-label">Peak Hour</div>
          <div className="stat-value">8:00 AM</div>
          <div className="stat-change negative-change">
            <span>↑ 1:25 longer than average</span>
          </div>
        </div>
      </div>

      <div className="dashboard-card">
        <div className="card-header">
          <h2 className="card-title">Traffic Overview</h2>
          <select 
            className="border rounded p-2 text-sm"
            defaultValue="current"
          >
            <option value="current">Current Week</option>
            <option value="previous">Previous Week</option>
          </select>
        </div>
        <p className="text-gray-600 mb-4">Weekly traffic data from camera captures</p>
        
        <div className="h-80 mb-6">
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
        
        <div className="flex justify-between items-center">
          <div>
            <p className="text-sm text-gray-600">Total weekly vehicles</p>
            <p className="text-xl font-bold">${totalWeeklyVehicles.toLocaleString()}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-600">Daily Cars Passing By</p>
            <p className="text-xl font-bold">7,842</p>
            <p className="text-sm text-green-600">+5.2% from last week</p>
          </div>
        </div>
      </div>

      <div className="dashboard-card mt-6">
        <div className="card-header">
          <h2 className="card-title">Peak Hour Traffic</h2>
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
    </div>
  );
}

export default Home;