// src/pages/VehiclesPassing.js
import React, { useState, useEffect } from "react";
import axios from "axios";
import { Bar } from "react-chartjs-2";
import { 
  Chart as ChartJS, 
  CategoryScale, 
  LinearScale, 
  BarElement,
  Title, 
  Tooltip, 
  Legend 
} from "chart.js";

ChartJS.register(
  CategoryScale, 
  LinearScale, 
  BarElement,
  Title, 
  Tooltip, 
  Legend
);

// API Base URL Configuration
const API_BASE_URL = process.env.NODE_ENV === 'development' 
  ? 'http://127.0.0.1:8000' 
  : '';

function VehiclesPassing() {
  const [timePeriod, setTimePeriod] = useState("today");
  const [vehicleData, setVehicleData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [locationFilter, setLocationFilter] = useState("all");
  const [locations, setLocations] = useState([]);
  const [dateRange, setDateRange] = useState("last_7_days");
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [dateGroups, setDateGroups] = useState([]);

  useEffect(() => {
    fetchLocations();
    fetchVehicleData();
  }, [timePeriod, locationFilter, dateRange, selectedGroup]);

  const fetchLocations = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/locations/`);
      setLocations(response.data);
    } catch (err) {
      console.error("Error fetching locations:", err);
    }
  };

  const fetchDateGroups = async (locationId) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/locations/${locationId}/groups/`);
      setDateGroups(response.data);
    } catch (err) {
      console.error("Error fetching date groups:", err);
    }
  };

  const fetchVehicleData = async () => {
    try {
      setLoading(true);
      console.log("🔄 Fetching vehicle data with filters:", { timePeriod, locationFilter, dateRange, selectedGroup });
      
      // Build query parameters based on backend structure
      const params = new URLSearchParams();
      
      if (selectedGroup) {
        params.append('group_id', selectedGroup);
      } else {
        if (locationFilter && locationFilter !== "all") params.append('location_id', locationFilter);
        if (timePeriod && timePeriod !== "all") params.append('period', timePeriod);
        if (dateRange && dateRange !== "all") params.append('date_range', dateRange);
      }
      
      const url = `${API_BASE_URL}/api/vehicles/?${params}`;
      console.log("📡 API URL:", url);
      
      const response = await axios.get(url);
      const apiData = response.data;
      
      console.log("✅ Vehicle data received:", apiData);
      
      if (apiData && typeof apiData === 'object') {
        // Handle different possible API response structures
        let mappedData;
        
        // Check if the response has the expected structure from your backend
        if (apiData.today || apiData.yesterday || apiData.week || apiData.month) {
          // This is the aggregated format with time periods
          const currentPeriodData = apiData[timePeriod] || {};
          
          mappedData = {
            cars: currentPeriodData.cars || currentPeriodData.car_count || 0,
            trucks: currentPeriodData.trucks || currentPeriodData.truck_count || 0,
            motorcycles: currentPeriodData.motorcycles || currentPeriodData.motorcycle_count || 0,
            jeeps: currentPeriodData.jeeps || currentPeriodData.bus_count || 0,
            tricycles: currentPeriodData.tricycles || currentPeriodData.bicycle_count || 0,
            other: currentPeriodData.other || currentPeriodData.other_count || 0,
            total: currentPeriodData.total || currentPeriodData.total_vehicles || 0,
            directional_total: currentPeriodData.directional_count || 0,
            summary: apiData.summary || {
              total_analyses: 0,
              average_daily: 0,
              data_source: 'Traffic Analysis Database'
            }
          };
        } else {
          // This is a single analysis/group format
          mappedData = {
            cars: apiData.car_count || apiData.cars || 0,
            trucks: apiData.truck_count || apiData.trucks || 0,
            motorcycles: apiData.motorcycle_count || apiData.motorcycles || 0,
            jeeps: apiData.bus_count || apiData.jeeps || 0,  // bus_count in DB = jeep
            tricycles: apiData.bicycle_count || apiData.tricycles || 0, // bicycle_count = tricycle
            other: apiData.other_count || apiData.other || 0,
            total: apiData.total_vehicles || apiData.total || 0,
            directional_total: apiData.directional_count || apiData.directional_total || 0,
            location: apiData.location_name || apiData.location,
            date: apiData.analysis_date || apiData.date,
            summary: {
              total_analyses: apiData.total_analyses || 1,
              average_daily: apiData.average_daily || 0,
              data_source: apiData.data_source || 'Traffic Analysis',
              peak_hour: apiData.peak_hour,
              congestion_level: apiData.congestion_level
            }
          };
        }
        
        // Calculate total if not provided
        if (mappedData.total === 0) {
          mappedData.total = mappedData.cars + mappedData.trucks + mappedData.motorcycles + 
                             mappedData.jeeps + mappedData.tricycles + mappedData.other;
        }
        
        setVehicleData(mappedData);
        
        // If location is selected and has groups, fetch them
        if (locationFilter !== "all") {
          fetchDateGroups(locationFilter);
        }
        
        setError(null);
      } else {
        console.log("❌ Invalid API response structure");
        setVehicleData(getEmptyVehicleData());
        setError("Invalid data format from server");
      }
      
    } catch (err) {
      console.error("🔴 API error:", err);
      console.error("🔴 Error response:", err.response);
      
      const errorMsg = err.response?.data?.error || err.message || "Failed to load vehicle data";
      setError(`API Error: ${errorMsg}`);
      
      // Set fallback empty data
      setVehicleData(getEmptyVehicleData());
    } finally {
      setLoading(false);
    }
  };

  const getEmptyVehicleData = () => ({
    cars: 0,
    trucks: 0,
    motorcycles: 0,
    jeeps: 0,
    tricycles: 0,
    other: 0,
    total: 0,
    directional_total: 0,
    summary: { 
      total_analyses: 0, 
      average_daily: 0, 
      data_source: 'Check if videos have been processed and analyzed'
    }
  });

  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading vehicle data...</div>
            <div style={{
              width: '40px',
              height: '40px',
              border: '4px solid #f3f3f3',
              borderTop: '4px solid #3b82f6',
              borderRadius: '50%',
              margin: '0 auto',
              animation: 'spin 1s linear infinite'
            }}></div>
          </div>
        </div>
      </div>
    );
  }

  // Use current data or empty defaults
  const currentData = vehicleData || getEmptyVehicleData();
  const totalVehicles = currentData.total || 0;
  const directionalTotal = currentData.directional_total || 0;

  // Log the data to verify it's being populated
  console.log("📊 Current vehicle data for display:", currentData);

  // Bar chart data for Vehicle Type Distribution only
  const barChartData = {
    labels: ['Cars', 'Trucks', 'Motorcycles', 'Jeeps', 'Tricycles', 'Other'],
    datasets: [
      {
        label: 'Vehicle Count',
        data: [
          currentData.cars || 0,
          currentData.trucks || 0,
          currentData.motorcycles || 0,
          currentData.jeeps || 0,
          currentData.tricycles || 0,
          currentData.other || 0
        ],
        backgroundColor: [
          'rgba(54, 162, 235, 0.7)',
          'rgba(255, 99, 132, 0.7)',
          'rgba(255, 159, 64, 0.7)',
          'rgba(75, 192, 192, 0.7)',
          'rgba(153, 102, 255, 0.7)',
          'rgba(201, 203, 207, 0.7)'
        ],
        borderColor: [
          'rgb(54, 162, 235)',
          'rgb(255, 99, 132)',
          'rgb(255, 159, 64)',
          'rgb(75, 192, 192)',
          'rgb(153, 102, 255)',
          'rgb(201, 203, 207)'
        ],
        borderWidth: 1
      }
    ]
  };

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Vehicle Composition Analysis
        </h1>
        <p style={{ color: '#666', margin: 0 }}>Detailed breakdown of vehicle types from traffic analysis</p>
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

      {/* Filters Section */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#2d3748', margin: 0 }}>
            Vehicle Type Distribution
          </h2>
          <button 
            onClick={fetchVehicleData}
            style={{
              padding: '8px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: 'white',
              color: '#374151',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            🔄 Refresh Data
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>Time Period</label>
            <select 
              className="select-input"
              value={timePeriod}
              onChange={(e) => {
                setTimePeriod(e.target.value);
                setSelectedGroup(null);
              }}
              style={{ width: '100%' }}
            >
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
              <option value="all">All Time</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>Location</label>
            <select 
              className="select-input"
              value={locationFilter}
              onChange={(e) => {
                setLocationFilter(e.target.value);
                setSelectedGroup(null);
                if (e.target.value !== "all") {
                  fetchDateGroups(e.target.value);
                } else {
                  setDateGroups([]);
                }
              }}
              style={{ width: '100%' }}
            >
              <option value="all">All Locations</option>
              {locations.map(location => (
                <option key={location.id} value={location.id}>
                  {location.display_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>Date Range</label>
            <select 
              className="select-input"
              value={dateRange}
              onChange={(e) => {
                setDateRange(e.target.value);
                setSelectedGroup(null);
              }}
              style={{ width: '100%' }}
            >
              <option value="last_7_days">Last 7 Days</option>
              <option value="last_30_days">Last 30 Days</option>
              <option value="last_90_days">Last 90 Days</option>
              <option value="all">All Time</option>
            </select>
          </div>

          {dateGroups.length > 0 && (
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>Date Group</label>
              <select 
                className="select-input"
                value={selectedGroup || ''}
                onChange={(e) => setSelectedGroup(e.target.value || null)}
                style={{ width: '100%' }}
              >
                <option value="">All Groups</option>
                {dateGroups.map(group => (
                  <option key={group.id} value={group.id}>
                    {group.date} - {group.get_time_range?.() || 'No time range'}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Data Source Info */}
        {currentData.summary && (
          <div style={{ 
            marginTop: '16px', 
            padding: '12px', 
            backgroundColor: '#f0f9ff',
            borderRadius: '6px',
            border: '1px solid #bae6fd'
          }}>
            <div style={{ fontSize: '14px', color: '#0369a1' }}>
              <strong>Data Source:</strong> {currentData.summary.data_source} • 
              <strong> Total Analyses:</strong> {currentData.summary.total_analyses || 0} • 
              <strong> Total Vehicles:</strong> {totalVehicles.toLocaleString()}
              {currentData.summary.average_daily > 0 && (
                <> • <strong>Avg Daily:</strong> {currentData.summary.average_daily.toLocaleString()}</>
              )}
              {currentData.summary.congestion_level && (
                <> • <strong>Congestion:</strong> {currentData.summary.congestion_level}</>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Total Vehicles Card */}
      <div style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: '12px',
        padding: '24px',
        color: 'white',
        marginBottom: '32px',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <p style={{ fontSize: '14px', opacity: 0.9, margin: '0 0 8px 0' }}>Total Vehicles ({timePeriod})</p>
            <p style={{ fontSize: '36px', fontWeight: 'bold', margin: '0 0 8px 0' }}>
              {totalVehicles.toLocaleString()}
            </p>
            {directionalTotal > 0 && (
              <p style={{ fontSize: '14px', opacity: 0.9, margin: 0 }}>
                {directionalTotal.toLocaleString()} vehicles counted directionally
              </p>
            )}
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ fontSize: '14px', opacity: 0.9, margin: '0 0 8px 0' }}>
              Period: {timePeriod.charAt(0).toUpperCase() + timePeriod.slice(1)}
            </p>
            <p style={{ fontSize: '16px', fontWeight: '600', margin: 0 }}>
              {currentData.location || 'All Locations'}
            </p>
            {currentData.date && (
              <p style={{ fontSize: '12px', opacity: 0.8, margin: '4px 0 0 0' }}>
                As of {new Date(currentData.date).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>
        
        {/* Show message when no vehicle data */}
        {totalVehicles === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '20px',
            backgroundColor: 'rgba(255,255,255,0.1)',
            borderRadius: '8px',
            marginTop: '16px'
          }}>
            <p style={{ margin: 0, fontSize: '14px', opacity: 0.9 }}>
              No vehicle data found. Process some traffic videos first.
            </p>
          </div>
        )}
      </div>

      {/* Vehicle Statistics Grid */}
      <div className="stats-grid">
        {[
          { label: 'Cars', value: currentData.cars, color: '#3b82f6' },
          { label: 'Trucks', value: currentData.trucks, color: '#ef4444' },
          { label: 'Motorcycles', value: currentData.motorcycles, color: '#f59e0b' },
          { label: 'Jeeps', value: currentData.jeeps, color: '#10b981' },
          { label: 'Tricycles', value: currentData.tricycles, color: '#8b5cf6' },
          { label: 'Other', value: currentData.other, color: '#6b7280' }
        ].map((item, index) => (
          <div className="stat-card" key={index}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <div className="stat-value" style={{ color: (item.value || 0) === 0 ? '#9ca3af' : '#2d3748' }}>
                  {(item.value || 0).toLocaleString()}
                </div>
                <div className="stat-label">{item.label}</div>
              </div>
              <div style={{ 
                width: '40px', 
                height: '40px', 
                borderRadius: '8px',
                backgroundColor: item.color,
                opacity: 0.2
              }} />
            </div>
            <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
              {((item.value / totalVehicles) * 100 || 0).toFixed(1)}% of total
            </div>
          </div>
        ))}
      </div>

      {/* Vehicle Type Distribution Chart - Main Chart */}
      <div style={{ marginBottom: '32px' }}>
        <div className="dashboard-card">
          <div className="card-header">
            <h3 className="card-title">Vehicle Type Distribution</h3>
            <p style={{ fontSize: '14px', color: '#666' }}>
              Total Vehicles: {totalVehicles.toLocaleString()} | 
              Directional Count: {directionalTotal.toLocaleString()}
            </p>
          </div>
          <div style={{ height: '400px', padding: '20px' }}>
            {totalVehicles > 0 ? (
              <Bar 
                data={barChartData} 
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { 
                    legend: { display: false },
                    tooltip: {
                      callbacks: {
                        label: function(context) {
                          let label = context.dataset.label || '';
                          let value = context.raw || 0;
                          let percentage = ((value / totalVehicles) * 100).toFixed(1);
                          return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                        }
                      }
                    }
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      title: {
                        display: true,
                        text: 'Number of Vehicles'
                      },
                      ticks: {
                        callback: function(value) {
                          return value.toLocaleString();
                        }
                      }
                    }
                  }
                }}
              />
            ) : (
              <div style={{ 
                height: '100%', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                color: '#666',
                fontSize: '16px'
              }}>
                No vehicle data available to display
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detailed Table */}
      <div className="dashboard-card">
        <div className="card-header">
          <h3 className="card-title">Detailed Vehicle Breakdown</h3>
          <p style={{ fontSize: '14px', color: '#666' }}>Generated: {new Date().toLocaleDateString()}</p>
        </div>
        
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Vehicle Type</th>
                <th>Count</th>
                <th>Percentage</th>
                <th>Directional Count</th>
                <th>% of Directional</th>
              </tr>
            </thead>
            <tbody>
              {[
                { type: 'Cars', data: currentData.cars },
                { type: 'Trucks', data: currentData.trucks },
                { type: 'Motorcycles', data: currentData.motorcycles },
                { type: 'Jeeps', data: currentData.jeeps },
                { type: 'Tricycles', data: currentData.tricycles },
                { type: 'Other', data: currentData.other }
              ].map((vehicle, index) => {
                const percentage = totalVehicles > 0 ? ((vehicle.data || 0) / totalVehicles * 100).toFixed(1) : '0.0';
                const directionalPercentage = directionalTotal > 0 ? ((vehicle.data || 0) / directionalTotal * 100).toFixed(1) : '0.0';
                
                return (
                  <tr key={index}>
                    <td style={{ fontWeight: '600' }}>{vehicle.type}</td>
                    <td>{(vehicle.data || 0).toLocaleString()}</td>
                    <td>{percentage}%</td>
                    <td>
                      {directionalTotal > 0 
                        ? Math.round((vehicle.data || 0) * (directionalTotal / totalVehicles)).toLocaleString()
                        : 'N/A'
                      }
                    </td>
                    <td>{directionalPercentage}%</td>
                  </tr>
                );
              })}
              {/* Total row */}
              <tr style={{ backgroundColor: '#f9fafb', fontWeight: 'bold' }}>
                <td>TOTAL</td>
                <td>{totalVehicles.toLocaleString()}</td>
                <td>100%</td>
                <td>{directionalTotal.toLocaleString()}</td>
                <td>100%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default VehiclesPassing;