import React, { useState, useEffect } from "react";
import axios from "axios";
import { Bar, Pie } from "react-chartjs-2";
import { 
  Chart as ChartJS, 
  CategoryScale, 
  LinearScale, 
  BarElement, 
  ArcElement,
  Title, 
  Tooltip, 
  Legend 
} from "chart.js";

ChartJS.register(
  CategoryScale, 
  LinearScale, 
  BarElement,
  ArcElement,
  Title, 
  Tooltip, 
  Legend
);

function VehiclesPassing() {
  const [timePeriod, setTimePeriod] = useState("today");
  const [vehicleData, setVehicleData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [locationFilter, setLocationFilter] = useState("all");
  const [locations, setLocations] = useState([]);
  const [dateRange, setDateRange] = useState("last_7_days");

  useEffect(() => {
    fetchVehicleData();
    fetchLocations();
  }, [timePeriod, locationFilter, dateRange]);

  const fetchLocations = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/locations/");
      setLocations(response.data);
    } catch (err) {
      console.error("Error fetching locations:", err);
    }
  };

const fetchVehicleData = async () => {
  try {
    setLoading(true);
    console.log("🔄 Fetching vehicle data with filters:", { timePeriod, locationFilter, dateRange });
    
    // Build query parameters
    const params = new URLSearchParams();
    if (timePeriod && timePeriod !== "all") params.append('period', timePeriod);
    if (locationFilter && locationFilter !== "all") params.append('location_id', locationFilter);
    if (dateRange && dateRange !== "all") params.append('date_range', dateRange);
    
    const url = `http://127.0.0.1:8000/api/vehicles/?${params}`;
    console.log("📡 API URL:", url);
    
    const response = await axios.get(url);
    const apiData = response.data;
    
    console.log("✅ Vehicle data received:", apiData);
    
    if (apiData && typeof apiData === 'object') {
      // Ensure all required fields exist
      const validatedData = {
        today: apiData.today || { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        yesterday: apiData.yesterday || { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        week: apiData.week || { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        month: apiData.month || { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        summary: apiData.summary || { total_analyses: 0, average_daily: 0, data_source: 'No data available' }
      };
      
      setVehicleData(validatedData);
      setError(null);
    } else {
      console.log("❌ Invalid API response structure");
      setVehicleData({
        today: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        yesterday: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        week: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        month: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
        summary: { total_analyses: 0, average_daily: 0, data_source: 'Invalid response format' }
      });
      setError("Invalid data format from server");
    }
    
  } catch (err) {
    console.error("🔴 API error:", err);
    console.error("🔴 Error response:", err.response);
    
    const errorMsg = err.response?.data?.error || err.message || "Failed to load vehicle data";
    setError(`API Error: ${errorMsg}`);
    
    // Set fallback data
    setVehicleData({
      today: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
      yesterday: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
      week: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
      month: { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 },
      summary: { 
        total_analyses: 0, 
        average_daily: 0, 
        data_source: 'Check if videos have been processed and analyzed',
        total_vehicles: 0,
        unique_days: 0
      }
    });
  } finally {
    setLoading(false);
  }
};

  const calculateChange = (current, previous) => {
    if (!previous || previous === 0) return { value: 0, isPositive: true };
    const change = ((current - previous) / previous) * 100;
    return {
      value: change,
      isPositive: change >= 0
    };
  };

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

  const currentData = vehicleData?.[timePeriod] || { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 };
  const previousData = timePeriod === "today" 
    ? (vehicleData?.yesterday || { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 })
    : (vehicleData?.today || { cars: 0, trucks: 0, buses: 0, motorcycles: 0, bicycles: 0, others: 0 });

  const carsChange = calculateChange(currentData.cars || 0, previousData?.cars || 0);
  const trucksChange = calculateChange(currentData.trucks || 0, previousData?.trucks || 0);
  const busesChange = calculateChange(currentData.buses || 0, previousData?.buses || 0);
  const motorcyclesChange = calculateChange(currentData.motorcycles || 0, previousData?.motorcycles || 0);
  const bicyclesChange = calculateChange(currentData.bicycles || 0, previousData?.bicycles || 0);
  const othersChange = calculateChange(currentData.others || 0, previousData?.others || 0);

  const totalVehicles = Object.values(currentData).reduce((sum, count) => sum + (count || 0), 0);

  const barChartData = {
    labels: ['Cars', 'Trucks', 'Buses', 'Motorcycles', 'Bicycles', 'Others'],
    datasets: [
      {
        label: 'Vehicle Count',
        data: [
          currentData.cars || 0,
          currentData.trucks || 0,
          currentData.buses || 0,
          currentData.motorcycles || 0,
          currentData.bicycles || 0,
          currentData.others || 0
        ],
        backgroundColor: [
          'rgba(54, 162, 235, 0.7)',
          'rgba(255, 99, 132, 0.7)',
          'rgba(75, 192, 192, 0.7)',
          'rgba(255, 159, 64, 0.7)',
          'rgba(153, 102, 255, 0.7)',
          'rgba(201, 203, 207, 0.7)'
        ],
        borderColor: [
          'rgb(54, 162, 235)',
          'rgb(255, 99, 132)',
          'rgb(75, 192, 192)',
          'rgb(255, 159, 64)',
          'rgb(153, 102, 255)',
          'rgb(201, 203, 207)'
        ],
        borderWidth: 1
      }
    ]
  };

  const pieChartData = {
    labels: ['Cars', 'Trucks', 'Buses', 'Motorcycles', 'Bicycles', 'Others'],
    datasets: [
      {
        data: [
          currentData.cars || 0,
          currentData.trucks || 0,
          currentData.buses || 0,
          currentData.motorcycles || 0,
          currentData.bicycles || 0,
          currentData.others || 0
        ],
        backgroundColor: [
          'rgba(54, 162, 235, 0.7)',
          'rgba(255, 99, 132, 0.7)',
          'rgba(75, 192, 192, 0.7)',
          'rgba(255, 159, 64, 0.7)',
          'rgba(153, 102, 255, 0.7)',
          'rgba(201, 203, 207, 0.7)'
        ],
        borderWidth: 1
      }
    ]
  };

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Vehicle Analytics
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
            Vehicle Statistics
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
              onChange={(e) => setTimePeriod(e.target.value)}
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
              onChange={(e) => setLocationFilter(e.target.value)}
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
              onChange={(e) => setDateRange(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="last_7_days">Last 7 Days</option>
              <option value="last_30_days">Last 30 Days</option>
              <option value="last_90_days">Last 90 Days</option>
              <option value="all">All Time</option>
            </select>
          </div>
        </div>

        {/* Data Source Info */}
        {vehicleData?.summary && (
          <div style={{ 
            marginTop: '16px', 
            padding: '12px', 
            backgroundColor: '#f0f9ff',
            borderRadius: '6px',
            border: '1px solid #bae6fd'
          }}>
            <div style={{ fontSize: '14px', color: '#0369a1' }}>
              <strong>Data Source:</strong> {vehicleData.summary.data_source || 'Traffic Analysis'} • 
              <strong> Total Analyses:</strong> {vehicleData.summary.total_analyses || 0} • 
              <strong> Avg Daily:</strong> {vehicleData.summary.average_daily?.toLocaleString() || 0} vehicles
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
            <p style={{ fontSize: '14px', opacity: 0.9, margin: 0 }}>
              {vehicleData?.summary?.data_source || 'From processed traffic videos'}
            </p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <p style={{ fontSize: '14px', opacity: 0.9, margin: '0 0 8px 0' }}>
              Period: {timePeriod.charAt(0).toUpperCase() + timePeriod.slice(1)}
            </p>
            <p style={{ fontSize: '16px', fontWeight: '600', margin: 0 }}>
              {timePeriod === "today" ? "Live Data" : "Historical Data"}
            </p>
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
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value" style={{ color: (currentData.cars || 0) === 0 ? '#9ca3af' : '#2d3748' }}>
                {(currentData.cars || 0).toLocaleString()}
              </div>
              <div className="stat-label">Cars</div>
            </div>
            {(currentData.cars || 0) > 0 ? (
              <div className={`stat-change ${carsChange.isPositive ? 'positive-change' : 'negative-change'}`}>
                {carsChange.isPositive ? '↗' : '↘'} {Math.abs(carsChange.value).toFixed(1)}%
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>No data</div>
            )}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            {((currentData.cars / totalVehicles) * 100 || 0).toFixed(1)}% of total
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value" style={{ color: (currentData.trucks || 0) === 0 ? '#9ca3af' : '#2d3748' }}>
                {(currentData.trucks || 0).toLocaleString()}
              </div>
              <div className="stat-label">Trucks</div>
            </div>
            {(currentData.trucks || 0) > 0 ? (
              <div className={`stat-change ${trucksChange.isPositive ? 'positive-change' : 'negative-change'}`}>
                {trucksChange.isPositive ? '↗' : '↘'} {Math.abs(trucksChange.value).toFixed(1)}%
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>No data</div>
            )}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            {((currentData.trucks / totalVehicles) * 100 || 0).toFixed(1)}% of total
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value" style={{ color: (currentData.buses || 0) === 0 ? '#9ca3af' : '#2d3748' }}>
                {(currentData.buses || 0).toLocaleString()}
              </div>
              <div className="stat-label">Buses</div>
            </div>
            {(currentData.buses || 0) > 0 ? (
              <div className={`stat-change ${busesChange.isPositive ? 'positive-change' : 'negative-change'}`}>
                {busesChange.isPositive ? '↗' : '↘'} {Math.abs(busesChange.value).toFixed(1)}%
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>No data</div>
            )}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            {((currentData.buses / totalVehicles) * 100 || 0).toFixed(1)}% of total
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value" style={{ color: (currentData.motorcycles || 0) === 0 ? '#9ca3af' : '#2d3748' }}>
                {(currentData.motorcycles || 0).toLocaleString()}
              </div>
              <div className="stat-label">Motorcycles</div>
            </div>
            {(currentData.motorcycles || 0) > 0 ? (
              <div className={`stat-change ${motorcyclesChange.isPositive ? 'positive-change' : 'negative-change'}`}>
                {motorcyclesChange.isPositive ? '↗' : '↘'} {Math.abs(motorcyclesChange.value).toFixed(1)}%
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>No data</div>
            )}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            {((currentData.motorcycles / totalVehicles) * 100 || 0).toFixed(1)}% of total
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value" style={{ color: (currentData.bicycles || 0) === 0 ? '#9ca3af' : '#2d3748' }}>
                {(currentData.bicycles || 0).toLocaleString()}
              </div>
              <div className="stat-label">Bicycles</div>
            </div>
            {(currentData.bicycles || 0) > 0 ? (
              <div className={`stat-change ${bicyclesChange.isPositive ? 'positive-change' : 'negative-change'}`}>
                {bicyclesChange.isPositive ? '↗' : '↘'} {Math.abs(bicyclesChange.value).toFixed(1)}%
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>No data</div>
            )}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            {((currentData.bicycles / totalVehicles) * 100 || 0).toFixed(1)}% of total
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value" style={{ color: (currentData.others || 0) === 0 ? '#9ca3af' : '#2d3748' }}>
                {(currentData.others || 0).toLocaleString()}
              </div>
              <div className="stat-label">Other Vehicles</div>
            </div>
            {(currentData.others || 0) > 0 ? (
              <div className={`stat-change ${othersChange.isPositive ? 'positive-change' : 'negative-change'}`}>
                {othersChange.isPositive ? '↗' : '↘'} {Math.abs(othersChange.value).toFixed(1)}%
              </div>
            ) : (
              <div style={{ fontSize: '12px', color: '#9ca3af' }}>No data</div>
            )}
          </div>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            {((currentData.others / totalVehicles) * 100 || 0).toFixed(1)}% of total
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px', marginBottom: '32px' }}>
        <div className="dashboard-card">
          <div className="card-header">
            <h3 className="card-title">Vehicle Type Distribution</h3>
            <p style={{ fontSize: '14px', color: '#666' }}>Count by vehicle type</p>
          </div>
          <div style={{ height: '320px' }}>
            <Bar 
              data={barChartData} 
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
              }}
            />
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <h3 className="card-title">Vehicle Percentage Breakdown</h3>
            <p style={{ fontSize: '14px', color: '#666' }}>Percentage of total traffic</p>
          </div>
          <div style={{ height: '320px' }}>
            <Pie 
              data={pieChartData} 
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'bottom' }
                }
              }}
            />
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
                <th>Change</th>
                <th>Percentage</th>
                <th>Trend</th>
                <th>Daily Average</th>
              </tr>
            </thead>
            <tbody>
              {[
                { type: 'Cars', data: currentData.cars, change: carsChange },
                { type: 'Trucks', data: currentData.trucks, change: trucksChange },
                { type: 'Buses', data: currentData.buses, change: busesChange },
                { type: 'Motorcycles', data: currentData.motorcycles, change: motorcyclesChange },
                { type: 'Bicycles', data: currentData.bicycles, change: bicyclesChange },
                { type: 'Others', data: currentData.others, change: othersChange }
              ].map((vehicle, index) => (
                <tr key={index}>
                  <td style={{ fontWeight: '600' }}>{vehicle.type}</td>
                  <td>{(vehicle.data || 0).toLocaleString()}</td>
                  <td className={vehicle.change.isPositive ? 'positive-change' : 'negative-change'}>
                    {vehicle.change.isPositive ? '+' : ''}{Math.abs(vehicle.change.value).toFixed(1)}%
                  </td>
                  <td>{(((vehicle.data || 0) / totalVehicles) * 100).toFixed(1)}%</td>
                  <td>
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      fontSize: '12px',
                      fontWeight: '500',
                      backgroundColor: vehicle.change.isPositive ? '#d1fae5' : '#fee2e2',
                      color: vehicle.change.isPositive ? '#065f46' : '#991b1b'
                    }}>
                      {vehicle.change.isPositive ? '↗ Increasing' : '↘ Decreasing'}
                    </span>
                  </td>
                  <td>
                    {vehicleData?.summary?.average_daily ? 
                      Math.round((vehicle.data || 0) / (vehicleData.summary.average_daily / 6)) : 0}/day
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

export default VehiclesPassing;