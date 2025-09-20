// src/pages/VehiclesPassing.js
import React, { useState } from "react";
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

function VehiclesPassing() {
  const [timePeriod, setTimePeriod] = useState("today");

  // Sample data for demonstration
  const vehicleData = {
    today: {
      cars: 1245,
      trucks: 456,
      tricycles: 789,
      motorcycles: 934
    },
    yesterday: {
      cars: 1100,
      trucks: 420,
      tricycles: 750,
      motorcycles: 880
    }
  };

  const chartData = {
    labels: ['Cars', 'Trucks', 'Tricycles', 'Motorcycles'],
    datasets: [
      {
        label: 'Vehicle Count',
        data: [
          vehicleData.today.cars,
          vehicleData.today.trucks,
          vehicleData.today.tricycles,
          vehicleData.today.motorcycles
        ],
        backgroundColor: [
          'rgba(54, 162, 235, 0.7)',
          'rgba(255, 99, 132, 0.7)',
          'rgba(75, 192, 192, 0.7)',
          'rgba(255, 159, 64, 0.7)'
        ],
        borderColor: [
          'rgb(54, 162, 235)',
          'rgb(255, 99, 132)',
          'rgb(75, 192, 192)',
          'rgb(255, 159, 64)'
        ],
        borderWidth: 1
      }
    ]
  };

  const calculateChange = (current, previous) => {
    const change = ((current - previous) / previous) * 100;
    return {
      value: change,
      isPositive: change >= 0
    };
  };

  const carsChange = calculateChange(vehicleData.today.cars, vehicleData.yesterday.cars);
  const trucksChange = calculateChange(vehicleData.today.trucks, vehicleData.yesterday.trucks);
  const tricyclesChange = calculateChange(vehicleData.today.tricycles, vehicleData.yesterday.tricycles);
  const motorcyclesChange = calculateChange(vehicleData.today.motorcycles, vehicleData.yesterday.motorcycles);

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">Traffic Monitor</h1>
        <p className="text-gray-600">Detailed breakdown of different vehicle types</p>
      </header>

      <div className="flex justify-between items-center mb-6">
        <h2 className="section-title">Vehicles Passing</h2>
        <select 
          className="border rounded p-2 text-sm"
          value={timePeriod}
          onChange={(e) => setTimePeriod(e.target.value)}
        >
          <option value="today">Today</option>
          <option value="yesterday">Yesterday</option>
          <option value="week">This Week</option>
          <option value="month">This Month</option>
        </select>
      </div>

      <div className="stats-grid mb-8">
        <div className="stat-card">
          <div className="stat-value">{vehicleData.today.cars.toLocaleString()}</div>
          <div className="stat-label">Cars</div>
          <div className={carsChange.isPositive ? "stat-change positive-change" : "stat-change negative-change"}>
            {carsChange.isPositive ? "+" : ""}{carsChange.value.toFixed(1)}% from yesterday
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-value">{vehicleData.today.trucks.toLocaleString()}</div>
          <div className="stat-label">Trucks</div>
          <div className={trucksChange.isPositive ? "stat-change positive-change" : "stat-change negative-change"}>
            {trucksChange.isPositive ? "+" : ""}{trucksChange.value.toFixed(1)}% from yesterday
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-value">{vehicleData.today.tricycles.toLocaleString()}</div>
          <div className="stat-label">Tricycles</div>
          <div className={tricyclesChange.isPositive ? "stat-change positive-change" : "stat-change negative-change"}>
            {tricyclesChange.isPositive ? "+" : ""}{tricyclesChange.value.toFixed(1)}% from yesterday
          </div>
        </div>
        
        <div className="stat-card">
          <div className="stat-value">{vehicleData.today.motorcycles.toLocaleString()}</div>
          <div className="stat-label">Motorcycles</div>
          <div className={motorcyclesChange.isPositive ? "stat-change positive-change" : "stat-change negative-change"}>
            {motorcyclesChange.isPositive ? "+" : ""}{motorcyclesChange.value.toFixed(1)}% from yesterday
          </div>
        </div>
      </div>

      <div className="dashboard-card mb-8">
        <div className="card-header">
          <h3 className="card-title">Vehicle Type Distribution</h3>
        </div>
        <div className="h-96">
          <Bar 
            data={chartData} 
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
      </div>

      <div className="dashboard-card">
        <div className="card-header">
          <h3 className="card-title">Vehicles Passing Details</h3>
          <p className="text-sm text-gray-600">Generated: 2025/05/01</p>
        </div>
        
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Vehicle Type</th>
                <th>Count</th>
                <th>Change from Yesterday</th>
                <th>Percentage</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Cars</td>
                <td>{vehicleData.today.cars.toLocaleString()}</td>
                <td className={carsChange.isPositive ? "positive-change" : "negative-change"}>
                  {carsChange.isPositive ? "+" : ""}{Math.abs(vehicleData.today.cars - vehicleData.yesterday.cars).toLocaleString()}
                </td>
                <td>{((vehicleData.today.cars / Object.values(vehicleData.today).reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td>Trucks</td>
                <td>{vehicleData.today.trucks.toLocaleString()}</td>
                <td className={trucksChange.isPositive ? "positive-change" : "negative-change"}>
                  {trucksChange.isPositive ? "+" : ""}{Math.abs(vehicleData.today.trucks - vehicleData.yesterday.trucks).toLocaleString()}
                </td>
                <td>{((vehicleData.today.trucks / Object.values(vehicleData.today).reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td>Tricycles</td>
                <td>{vehicleData.today.tricycles.toLocaleString()}</td>
                <td className={tricyclesChange.isPositive ? "positive-change" : "negative-change"}>
                  {tricyclesChange.isPositive ? "+" : ""}{Math.abs(vehicleData.today.tricycles - vehicleData.yesterday.tricycles).toLocaleString()}
                </td>
                <td>{((vehicleData.today.tricycles / Object.values(vehicleData.today).reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td>Motorcycles</td>
                <td>{vehicleData.today.motorcycles.toLocaleString()}</td>
                <td className={motorcyclesChange.isPositive ? "positive-change" : "negative-change"}>
                  {motorcyclesChange.isPositive ? "+" : ""}{Math.abs(vehicleData.today.motorcycles - vehicleData.yesterday.motorcycles).toLocaleString()}
                </td>
                <td>{((vehicleData.today.motorcycles / Object.values(vehicleData.today).reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default VehiclesPassing;