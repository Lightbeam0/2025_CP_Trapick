// src/pages/VehiclesPassing.js
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

  const defaultVehicleData = {
    today: {
      cars: 1245,
      trucks: 456,
      buses: 123,
      motorcycles: 934,
      bicycles: 67,
      others: 89
    },
    yesterday: {
      cars: 1100,
      trucks: 420,
      buses: 115,
      motorcycles: 880,
      bicycles: 62,
      others: 78
    }
  };

  useEffect(() => {
    const fetchVehicleData = async () => {
      try {
        const response = await axios.get("http://127.0.0.1:8000/api/vehicles/");
        const apiData = response.data;
        
        if (apiData && typeof apiData === 'object') {
          const normalizedData = {
            today: {
              cars: apiData.today?.cars || apiData.cars || defaultVehicleData.today.cars,
              trucks: apiData.today?.trucks || apiData.trucks || defaultVehicleData.today.trucks,
              buses: apiData.today?.buses || apiData.buses || defaultVehicleData.today.buses,
              motorcycles: apiData.today?.motorcycles || apiData.motorcycles || defaultVehicleData.today.motorcycles,
              bicycles: apiData.today?.bicycles || apiData.bicycles || defaultVehicleData.today.bicycles,
              others: apiData.today?.others || apiData.others || defaultVehicleData.today.others
            },
            yesterday: defaultVehicleData.yesterday
          };
          
          setVehicleData(normalizedData);
        } else {
          setVehicleData(defaultVehicleData);
        }
        
        setLoading(false);
      } catch (err) {
        console.error("API error:", err);
        setError("Failed to load vehicle data. Using sample data for demonstration.");
        setVehicleData(defaultVehicleData);
        setLoading(false);
      }
    };

    fetchVehicleData();
  }, []);

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
          <div style={{ fontSize: '18px', color: '#666' }}>Loading vehicle data...</div>
        </div>
      </div>
    );
  }

  const currentData = vehicleData?.[timePeriod] || vehicleData?.today || defaultVehicleData.today;
  const previousData = timePeriod === "today" 
    ? (vehicleData?.yesterday || defaultVehicleData.yesterday)
    : (vehicleData?.today || defaultVehicleData.today);

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
          Traffic Monitor
        </h1>
        <p style={{ color: '#666', margin: 0 }}>Detailed breakdown of different vehicle types</p>
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
          Vehicles Passing
        </h2>
        <select 
          className="select-input"
          value={timePeriod}
          onChange={(e) => setTimePeriod(e.target.value)}
        >
          <option value="today">Today</option>
          <option value="yesterday">Yesterday</option>
          <option value="week">This Week</option>
          <option value="month">This Month</option>
        </select>
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
            <p style={{ fontSize: '14px', opacity: 0.9, margin: '0 0 8px 0' }}>Total Vehicles</p>
            <p style={{ fontSize: '36px', fontWeight: 'bold', margin: '0 0 8px 0' }}>
              {totalVehicles.toLocaleString()}
            </p>
            <p style={{ fontSize: '14px', opacity: 0.9, margin: 0 }}>Detected and counted automatically</p>
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
      </div>

      {/* Vehicle Statistics Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value">{(currentData.cars || 0).toLocaleString()}</div>
              <div className="stat-label">Cars</div>
            </div>
            <div className={`stat-change ${carsChange.isPositive ? 'positive-change' : 'negative-change'}`}>
              {carsChange.isPositive ? '↗' : '↘'} {carsChange.value.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value">{(currentData.trucks || 0).toLocaleString()}</div>
              <div className="stat-label">Trucks</div>
            </div>
            <div className={`stat-change ${trucksChange.isPositive ? 'positive-change' : 'negative-change'}`}>
              {trucksChange.isPositive ? '↗' : '↘'} {trucksChange.value.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value">{(currentData.buses || 0).toLocaleString()}</div>
              <div className="stat-label">Buses</div>
            </div>
            <div className={`stat-change ${busesChange.isPositive ? 'positive-change' : 'negative-change'}`}>
              {busesChange.isPositive ? '↗' : '↘'} {busesChange.value.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value">{(currentData.motorcycles || 0).toLocaleString()}</div>
              <div className="stat-label">Motorcycles</div>
            </div>
            <div className={`stat-change ${motorcyclesChange.isPositive ? 'positive-change' : 'negative-change'}`}>
              {motorcyclesChange.isPositive ? '↗' : '↘'} {motorcyclesChange.value.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value">{(currentData.bicycles || 0).toLocaleString()}</div>
              <div className="stat-label">Bicycles</div>
            </div>
            <div className={`stat-change ${bicyclesChange.isPositive ? 'positive-change' : 'negative-change'}`}>
              {bicyclesChange.isPositive ? '↗' : '↘'} {bicyclesChange.value.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="stat-value">{(currentData.others || 0).toLocaleString()}</div>
              <div className="stat-label">Other Vehicles</div>
            </div>
            <div className={`stat-change ${othersChange.isPositive ? 'positive-change' : 'negative-change'}`}>
              {othersChange.isPositive ? '↗' : '↘'} {othersChange.value.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px', marginBottom: '32px' }}>
        <div className="dashboard-card">
          <div className="card-header">
            <h3 className="card-title">Vehicle Type Distribution</h3>
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
          <h3 className="card-title">Vehicles Passing Details</h3>
          <p style={{ fontSize: '14px', color: '#666' }}>Generated: {new Date().toLocaleDateString()}</p>
        </div>
        
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Vehicle Type</th>
                <th>Count</th>
                <th>Change from Yesterday</th>
                <th>Percentage</th>
                <th>Trend</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: '600' }}>Cars</td>
                <td>{(currentData.cars || 0).toLocaleString()}</td>
                <td className={carsChange.isPositive ? 'positive-change' : 'negative-change'}>
                  {carsChange.isPositive ? '+' : ''}{Math.abs((currentData.cars || 0) - (previousData?.cars || 0)).toLocaleString()}
                </td>
                <td>{(((currentData.cars || 0) / totalVehicles) * 100).toFixed(1)}%</td>
                <td>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    fontWeight: '500',
                    backgroundColor: carsChange.isPositive ? '#d1fae5' : '#fee2e2',
                    color: carsChange.isPositive ? '#065f46' : '#991b1b'
                  }}>
                    {carsChange.isPositive ? '↗ Increasing' : '↘ Decreasing'}
                  </span>
                </td>
              </tr>
              {/* Add similar rows for other vehicle types */}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default VehiclesPassing;