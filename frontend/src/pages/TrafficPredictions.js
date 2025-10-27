// src/pages/TrafficPredictions.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const TrafficPredictions = () => {
  const [predictions, setPredictions] = useState([]);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState('');
  const [generating, setGenerating] = useState(false);

  // Set default date to tomorrow
  useEffect(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setSelectedDate(tomorrow.toISOString().split('T')[0]);
  }, []);

  const generatePredictions = async () => {
    setGenerating(true);
    try {
      await axios.post('http://127.0.0.1:8000/api/predictions/generate/');
      alert('Predictions generated successfully!');
      fetchPredictions();
      fetchInsights();
    } catch (error) {
      console.error('Error generating predictions:', error);
      alert('Error generating predictions: ' + (error.response?.data?.message || error.message));
    } finally {
      setGenerating(false);
    }
  };

  const fetchPredictions = async () => {
    if (!selectedDate) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`http://127.0.0.1:8000/api/predictions/?date=${selectedDate}`);
      setPredictions(response.data.predictions);
    } catch (error) {
      console.error('Error fetching predictions:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchInsights = async () => {
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/predictions/insights/');
      setInsights(response.data);
    } catch (error) {
      console.error('Error fetching insights:', error);
    }
  };

  useEffect(() => {
    fetchPredictions();
    fetchInsights();
  }, [selectedDate]);

  const getCongestionColor = (level) => {
    const colors = {
      'severe': '#dc2626',
      'high': '#ea580c', 
      'medium': '#d97706',
      'low': '#16a34a',
      'very_low': '#6b7280'
    };
    return colors[level] || '#6b7280';
  };

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Traffic Predictions
        </h1>
        <p style={{ color: '#666', margin: 0 }}>AI-powered traffic forecasting based on historical patterns</p>
      </header>

      {/* Generate Predictions Card */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600' }}>Generate Predictions</h2>
          <button 
            onClick={generatePredictions}
            disabled={generating}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: generating ? '#9ca3af' : '#3b82f6',
              color: 'white',
              cursor: generating ? 'not-allowed' : 'pointer',
              fontWeight: '500'
            }}
          >
            {generating ? 'Generating...' : 'Generate New Predictions'}
          </button>
        </div>
        <p style={{ color: '#666', fontSize: '14px' }}>
          Generate traffic predictions based on historical vehicle detection data. 
          This analyzes patterns from your processed videos to forecast future traffic.
        </p>
      </div>

      {/* Insights Card */}
      {insights && (
        <div className="dashboard-card" style={{ marginBottom: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Prediction Insights</h2>
          
          {insights.overall_peak && (
            <div style={{ 
              backgroundColor: '#f0f9ff', 
              padding: '16px', 
              borderRadius: '8px',
              marginBottom: '16px'
            }}>
              <h3 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '8px' }}>🚦 Peak Traffic Prediction</h3>
              <p style={{ margin: 0, color: '#374151' }}>
                <strong>{insights.overall_peak.vehicles} vehicles</strong> expected at <strong>{insights.overall_peak.hour}</strong> on {insights.overall_peak.date}
              </p>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            {insights.next_3_days.map(day => (
              <div key={day.date} style={{ 
                padding: '16px', 
                backgroundColor: '#f8fafc',
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <div style={{ fontWeight: '600', marginBottom: '8px' }}>{day.day_name}</div>
                <div style={{ fontSize: '14px', color: '#666' }}>
                  <div>Peak: {day.peak_hour} ({day.peak_vehicles} vehicles)</div>
                  <div>Avg: {day.average_vehicles} vehicles/hour</div>
                  <div>Confidence: {(day.average_confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Peak Hours by Day */}
      {insights && insights.peak_hours_by_day && (
        <div className="dashboard-card" style={{ marginBottom: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Peak Traffic Hours</h2>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
            {Object.entries(insights.peak_hours_by_day).map(([dayName, peakHours]) => (
              <div key={dayName} style={{ 
                padding: '16px', 
                backgroundColor: '#f8fafc',
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <h3 style={{ fontWeight: '600', marginBottom: '12px', color: '#374151' }}>{dayName}</h3>
                {peakHours.map((peak, index) => (
                  <div key={index} style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    marginBottom: '8px',
                    padding: '8px',
                    backgroundColor: 'white',
                    borderRadius: '4px'
                  }}>
                    <span style={{ fontWeight: '500' }}>{peak.hour}</span>
                    <span style={{ 
                      fontWeight: '600', 
                      color: '#dc2626',
                      fontSize: '14px'
                    }}>
                      {peak.vehicles} vehicles
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Predictions Table */}
      <div className="dashboard-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600' }}>Hourly Predictions</h2>
          <input 
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          />
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div style={{ fontSize: '16px', color: '#666' }}>Loading predictions...</div>
          </div>
        ) : predictions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
            No predictions available for selected date. Generate predictions first.
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Predicted Vehicles</th>
                  <th>Congestion Level</th>
                  <th>Confidence</th>
                  <th>Confidence Range</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map(prediction => (
                  <tr key={prediction.id}>
                    <td style={{ fontWeight: '600' }}>{prediction.hour_display}</td>
                    <td>{prediction.predicted_vehicle_count}</td>
                    <td>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        padding: '4px 12px',
                        borderRadius: '16px',
                        fontSize: '12px',
                        fontWeight: '600',
                        backgroundColor: getCongestionColor(prediction.predicted_congestion) + '20',
                        color: getCongestionColor(prediction.predicted_congestion)
                      }}>
                        {prediction.predicted_congestion}
                      </span>
                    </td>
                    <td>{(prediction.confidence_score * 100).toFixed(0)}%</td>
                    <td style={{ fontSize: '12px', color: '#666' }}>
                      {prediction.confidence_interval_lower.toFixed(0)} - {prediction.confidence_interval_upper.toFixed(0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default TrafficPredictions;