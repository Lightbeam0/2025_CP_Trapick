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

  useEffect(() => {
    const fetchOverviewData = async () => {
      try {
        const response = await axios.get("http://127.0.0.1:8000/api/analyze/");
        
        // Handle case where we have real data but it's all zeros
        if (response.data.weekly_data && response.data.weekly_data.every(val => val === 0)) {
          setOverviewData({
            ...response.data,
            hasData: false, // Flag to show "no data" state
            message: "No traffic data available yet. Upload videos to see analysis results."
          });
        } else {
          setOverviewData({
            ...response.data,
            hasData: true // Flag to show real data
          });
        }
        
        setLoading(false);
      } catch (err) {
        console.error("API error:", err);
        setError("Failed to load traffic data");
        setLoading(false);
      }
    };

    fetchOverviewData();
  }, []);

  // Show loading state
  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ fontSize: '18px', color: '#666' }}>Loading real traffic data...</div>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="main-content">
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ color: '#ef4444', fontSize: '18px', marginBottom: '16px' }}>{error}</div>
          <button onClick={() => window.location.reload()} className="button button-primary">
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Show "no data" state
  if (overviewData && !overviewData.hasData) {
    return (
      <div className="main-content">
        <header style={{ marginBottom: '32px' }}>
          <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
            Traffic Monitor
          </h1>
          <p style={{ color: '#666', margin: 0 }}>System Ready - Waiting for Data</p>
        </header>

        <div className="dashboard-card" style={{ textAlign: 'center', padding: '60px' }}>
          <div style={{ fontSize: '48px', marginBottom: '20px' }}>📊</div>
          <h2 style={{ fontSize: '24px', marginBottom: '16px', color: '#4b5563' }}>
            No Traffic Data Yet
          </h2>
          <p style={{ color: '#6b7280', marginBottom: '24px', fontSize: '16px' }}>
            {overviewData.message}
          </p>
          <p style={{ color: '#9ca3af', fontSize: '14px' }}>
            Upload traffic videos to start generating analysis reports and visualizations.
          </p>
        </div>
      </div>
    );
  }

  const weeklyData = overviewData?.weekly_data || [0, 0, 0, 0, 0, 0, 0];
  const totalWeeklyVehicles = overviewData?.total_vehicles || 0;

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
        <p style={{ color: '#666', marginBottom: '16px' }}>Weekly traffic patterns based on processed video dates</p>
        
        <div style={{ height: '320px', marginBottom: '24px' }}>
          <Line
            data={{
              labels: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
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
          <p style={{ fontSize: '14px', color: '#666' }}>Busiest times based on analyzed traffic patterns</p>
        </div>
        
        {overviewData.areas && overviewData.areas.length > 0 ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
            {overviewData.areas.map((area, index) => (
              <div key={index} className="area-card" style={{
                backgroundColor: '#f8fafc',
                padding: '20px',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                position: 'relative'
              }}>
                {/* Status indicator */}
                <div style={{
                  position: 'absolute',
                  top: '12px',
                  right: '12px',
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: area.total_analysis_vehicles > 0 ? '#10b981' : '#f59e0b'
                }}></div>
                
                <h3 style={{ 
                  fontSize: '18px', 
                  fontWeight: '600', 
                  marginBottom: '16px',
                  color: area.name.includes('No data') || area.name.includes('Error') ? '#9ca3af' : '#1f2937'
                }}>
                  {area.name}
                  {area.total_analysis_vehicles > 0 && (
                    <span style={{ 
                      fontSize: '12px', 
                      color: '#6b7280', 
                      fontWeight: 'normal',
                      marginLeft: '8px'
                    }}>
                      ({area.total_analysis_vehicles.toLocaleString()} vehicles)
                    </span>
                  )}
                </h3>
                
                {/* Morning Peak */}
                <div style={{ marginBottom: '20px' }}>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    marginBottom: '8px' 
                  }}>
                    <span style={{ fontSize: '14px', color: '#4b5563', fontWeight: '500' }}>
                      🌅 Morning Peak
                    </span>
                    <span style={{ 
                      fontSize: '14px', 
                      fontWeight: '600', 
                      color: area.morning_volume > 0 ? '#dc2626' : '#9ca3af',
                      backgroundColor: area.morning_volume > 0 ? '#fef2f2' : '#f3f4f6',
                      padding: '4px 8px',
                      borderRadius: '4px'
                    }}>
                      {area.morning_peak}
                    </span>
                  </div>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center' 
                  }}>
                    <span style={{ fontSize: '14px', color: '#6b7280' }}>
                      Average vehicles:
                    </span>
                    <span style={{ 
                      fontSize: '14px', 
                      fontWeight: '600', 
                      color: area.morning_volume > 0 ? '#1f2937' : '#9ca3af'
                    }}>
                      {area.morning_volume > 0 ? area.morning_volume.toLocaleString() + '/hr' : 'No data'}
                    </span>
                  </div>
                </div>
                
                {/* Evening Peak */}
                <div>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    marginBottom: '8px' 
                  }}>
                    <span style={{ fontSize: '14px', color: '#4b5563', fontWeight: '500' }}>
                      🌇 Evening Peak
                    </span>
                    <span style={{ 
                      fontSize: '14px', 
                      fontWeight: '600', 
                      color: area.evening_volume > 0 ? '#dc2626' : '#9ca3af',
                      backgroundColor: area.evening_volume > 0 ? '#fef2f2' : '#f3f4f6',
                      padding: '4px 8px',
                      borderRadius: '4px'
                    }}>
                      {area.evening_peak}
                    </span>
                  </div>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center' 
                  }}>
                    <span style={{ fontSize: '14px', color: '#6b7280' }}>
                      Average vehicles:
                    </span>
                    <span style={{ 
                      fontSize: '14px', 
                      fontWeight: '600', 
                      color: area.evening_volume > 0 ? '#1f2937' : '#9ca3af'
                    }}>
                      {area.evening_volume > 0 ? area.evening_volume.toLocaleString() + '/hr' : 'No data'}
                    </span>
                  </div>
                </div>
                
                {/* Data quality indicator */}
                {area.total_analysis_vehicles === 0 && (
                  <div style={{ 
                    marginTop: '16px', 
                    padding: '8px', 
                    backgroundColor: '#fffbeb',
                    border: '1px solid #fef3c7',
                    borderRadius: '4px',
                    fontSize: '12px',
                    color: '#92400e',
                    textAlign: 'center'
                  }}>
                    ⚡ Process traffic videos to see real peak hours
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ 
            textAlign: 'center', 
            padding: '40px', 
            color: '#6b7280',
            backgroundColor: '#f9fafb',
            borderRadius: '8px'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>📊</div>
            <h3 style={{ fontSize: '18px', marginBottom: '8px' }}>No Traffic Data Available</h3>
            <p style={{ fontSize: '14px', margin: 0 }}>
              Upload and process traffic videos to see peak hour analysis.
            </p>
          </div>
        )}
        
        {/* Helpful tip */}
        {(overviewData.areas && overviewData.areas.some(area => area.total_analysis_vehicles > 0)) && (
          <div style={{ 
            marginTop: '20px', 
            padding: '12px', 
            backgroundColor: '#f0f9ff',
            border: '1px solid #bae6fd',
            borderRadius: '6px',
            fontSize: '14px',
            color: '#0369a1'
          }}>
            💡 <strong>Tip:</strong> Peak hours are calculated from actual traffic patterns in your processed videos.
            {overviewData.areas.find(area => area.total_analysis_vehicles > 0) && 
              ` Based on ${overviewData.areas.find(area => area.total_analysis_vehicles > 0).total_analysis_vehicles.toLocaleString()} analyzed vehicles.`
            }
          </div>
        )}
      </div>
    </div>
  );
}

export default Home;