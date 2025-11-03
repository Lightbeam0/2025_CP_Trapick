// src/pages/LocationsList.js - UPDATED WITH DEBUGGING
import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

function LocationsList() {
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchLocations = async () => {
    try {
      setLoading(true);
      console.log("🔄 Fetching locations from API...");
      
      // Log the exact URL being called
      const apiUrl = "http://127.0.0.1:8000/api/locations/";
      console.log(`📡 Request URL: ${apiUrl}`);
      
      const response = await axios.get(apiUrl);
      console.log("✅ API Response received:", {
        status: response.status,
        headers: Object.fromEntries(Object.entries(response.headers).slice(0, 5)), // first 5 headers
        dataLength: Array.isArray(response.data) ? response.data.length : 'not array',
      });
      console.log("📊 Full response data:", response.data);

      // Validate response structure
      if (response.data && Array.isArray(response.data)) {
        setLocations(response.data);
        setError(null);
        console.log(`✅ Successfully loaded ${response.data.length} locations`);
      } else {
        const errorMsg = "Invalid response format: expected array";
        console.error("❌", errorMsg, "Received:", response.data);
        setError(errorMsg);
        setLocations([]);
      }
      
    } catch (err) {
      console.error("❌ Error fetching locations:", err);
      
      if (err.response) {
        console.error("❌ Server responded with error:");
        console.error("   Status:", err.response.status);
        console.error("   Data:", err.response.data);
        console.error("   Headers:", err.response.headers);
        
        let errorMessage = `Failed to load locations: ${err.response.status}`;
        if (err.response.data?.error) {
          errorMessage += ` - ${err.response.data.error}`;
        } else if (typeof err.response.data === 'string') {
          errorMessage += ` - ${err.response.data}`;
        }
        setError(errorMessage);
      } else if (err.request) {
        console.error("❌ No response received (network error?):", err.request);
        setError("Network error: Could not reach the server. Is it running?");
      } else {
        console.error("❌ Unexpected error:", err.message);
        setError(`Unexpected error: ${err.message}`);
      }
      
      setLocations([]);
    } finally {
      setLoading(false);
      console.log("🏁 Location fetch completed");
    }
  };

  const viewLocationGroups = (locationId) => {
    console.log(`📍 Navigating to groups for location ID: ${locationId}`);
    navigate(`/locations/${locationId}/groups`);
  };

  useEffect(() => {
    fetchLocations();
  }, []);

  // 🔍 Developer debug tip in console
  useEffect(() => {
    console.group("🛠️ Debug Tip");
    console.log("To test the locations API directly in browser console, run:");
    console.log('fetch("http://127.0.0.1:8000/api/locations/").then(r => r.json()).then(console.log)');
    console.log("Expected response: array of location objects with id, display_name, etc.");
    console.groupEnd();
  }, []);

  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading locations...</div>
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

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Locations
        </h1>
        <p style={{ color: '#666', margin: 0 }}>Select a location to view grouped videos by date</p>
      </header>

      {error && (
        <div style={{
          backgroundColor: '#fee2e2',
          border: '1px solid #fecaca',
          color: '#dc2626',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '24px'
        }}>
          {error}
        </div>
      )}

      {locations.length === 0 ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div style={{ fontSize: '64px', marginBottom: '16px', color: '#d1d5db' }}>📍</div>
          <h3 style={{ marginBottom: '12px', color: '#374151' }}>No Locations Found</h3>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>
            Create locations in the settings to organize your video analyses.
          </p>
          <button 
            onClick={() => navigate('/settings')}
            style={{
              padding: '12px 24px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: '#3b82f6',
              color: 'white',
              cursor: 'pointer',
              fontWeight: '500',
              fontSize: '16px'
            }}
          >
            Go to Settings
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '20px' }}>
          {locations.map(location => (
            <div 
              key={location.id}
              className="dashboard-card"
              style={{
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                border: '2px solid transparent'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#3b82f6';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'transparent';
                e.currentTarget.style.transform = 'translateY(0)';
              }}
              onClick={() => viewLocationGroups(location.id)}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
                <div style={{
                  width: '60px',
                  height: '60px',
                  backgroundColor: '#3b82f6',
                  borderRadius: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '24px',
                  color: 'white',
                  flexShrink: 0
                }}>
                  📍
                </div>
                
                <div style={{ flex: 1 }}>
                  <h3 style={{ margin: '0 0 8px 0', color: '#1f2937', fontSize: '18px' }}>
                    {location.display_name}
                  </h3>
                  
                  {location.description && (
                    <p style={{ color: '#6b7280', margin: '0 0 12px 0', fontSize: '14px', lineHeight: '1.4' }}>
                      {location.description}
                    </p>
                  )}
                  
                  <div style={{ display: 'flex', gap: '16px', fontSize: '14px', color: '#666' }}>
                    <div>
                      <span style={{ fontWeight: '600' }}>Lat:</span> {location.latitude || 'N/A'}
                    </div>
                    <div>
                      <span style={{ fontWeight: '600' }}>Lng:</span> {location.longitude || 'N/A'}
                    </div>
                  </div>
                  
                  {location.processing_profile_details && (
                    <div style={{ marginTop: '8px' }}>
                      <span style={{
                        backgroundColor: '#f0f9ff',
                        color: '#0369a1',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: '500'
                      }}>
                        {location.processing_profile_details.display_name}
                      </span>
                    </div>
                  )}
                </div>
                
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ 
                    backgroundColor: '#f0f9ff', 
                    color: '#3b82f6',
                    padding: '8px 12px',
                    borderRadius: '20px',
                    fontSize: '14px',
                    fontWeight: '600'
                  }}>
                    View Groups →
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default LocationsList;