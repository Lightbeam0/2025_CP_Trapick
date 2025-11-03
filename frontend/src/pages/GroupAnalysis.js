// src/pages/GroupAnalysis.js - ESLint-FIXED & CLEANED
import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

function GroupAnalysis() {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const fetchGroups = async () => {
    try {
      setLoading(true);
      console.log("🔄 Fetching groups from /api/groups/...");
      
      const response = await axios.get("http://127.0.0.1:8000/api/groups/");
      console.log("✅ Groups received:", response.data);
      
      if (response.data && Array.isArray(response.data)) {
        setGroups(response.data);
        setError(null);
      } else {
        setError("Invalid response format from server");
        setGroups([]);
      }
    } catch (err) {
      console.error("❌ Error fetching groups:", err);
      setError(`Failed to load groups: ${err.message}`);
      setGroups([]);
    } finally {
      setLoading(false);
    }
  };

  const viewGroupDetail = (groupId) => {
    navigate(`/group-analysis/${groupId}`);
  };

  // Helper function to determine congestion level
  const getCongestionLevel = (vehicleCount) => {
    if (vehicleCount > 1000) return { level: 'SEVERE', color: '#dc2626', bgColor: '#fee2e2' };
    if (vehicleCount > 500) return { level: 'HIGH', color: '#ef4444', bgColor: '#fef2f2' };
    if (vehicleCount > 200) return { level: 'MEDIUM', color: '#d97706', bgColor: '#fef3c7' };
    return { level: 'LOW', color: '#059669', bgColor: '#d1fae5' };
  };

  useEffect(() => {
    fetchGroups();
  }, []); // Empty dependency array — runs once on mount

  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading location groups...</div>
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
          Location Analysis Groups
        </h1>
        <p style={{ color: '#666', margin: 0 }}>
          Videos automatically grouped by location and recording date
        </p>
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
          <div style={{ fontWeight: '600', marginBottom: '8px' }}>Error Loading Groups</div>
          <div style={{ marginBottom: '12px' }}>{error}</div>
          <button
            onClick={fetchGroups}
            style={{
              padding: '8px 16px',
              border: '1px solid #dc2626',
              borderRadius: '4px',
              backgroundColor: 'white',
              color: '#dc2626',
              cursor: 'pointer'
            }}
          >
            Try Again
          </button>
        </div>
      )}

      {groups.length === 0 && !loading && !error ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div style={{ fontSize: '64px', marginBottom: '16px', color: '#d1d5db' }}>📁</div>
          <h3 style={{ marginBottom: '12px', color: '#374151' }}>No Groups Found</h3>
          <p style={{ color: '#6b7280', marginBottom: '8px' }}>
            Processed videos will be automatically grouped by location and date.
          </p>
          <p style={{ color: '#9ca3af', fontSize: '14px', marginBottom: '24px' }}>
            Upload and process some videos to see them appear here.
          </p>
          <button 
            onClick={() => navigate('/')}
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
            Upload Videos
          </button>
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '600' }}>Location Groups</h2>
              <p style={{ color: '#666', margin: '4px 0 0 0', fontSize: '14px' }}>
                {groups.length} groups • {groups.reduce((total, group) => total + (group.video_count || 0), 0)} total videos
              </p>
            </div>
            <button
              onClick={fetchGroups}
              style={{
                padding: '8px 16px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              Refresh
            </button>
          </div>

          <div style={{ display: 'grid', gap: '16px' }}>
            {groups.map((group) => {
              // Safely access nested properties
              const locationName = group.location?.display_name || 'Unknown Location';
              const totalVehicles = group.total_vehicles || 0;
              const videoCount = group.video_count || 0;
              const congestion = getCongestionLevel(totalVehicles);

              return (
                <div 
                  key={group.id}
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
                  onClick={() => viewGroupDetail(group.id)}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                    <div style={{ flex: 1 }}>
                      <h3 style={{ margin: '0 0 8px 0', color: '#1f2937', fontSize: '20px' }}>
                        {locationName}
                      </h3>
                      <p style={{ color: '#6b7280', margin: '0 0 8px 0', fontSize: '16px', fontWeight: '500' }}>
                        {new Date(group.date).toLocaleDateString('en-US', { 
                          weekday: 'long', 
                          year: 'numeric', 
                          month: 'long', 
                          day: 'numeric' 
                        })}
                      </p>
                      {group.time_range && group.time_range !== "No time data" && (
                        <p style={{ color: '#6b7280', margin: '0 0 8px 0', fontSize: '14px' }}>
                          🕒 {group.time_range}
                        </p>
                      )}
                    </div>
                    
                    <div style={{ textAlign: 'right' }}>
                      <span style={{
                        backgroundColor: congestion.bgColor,
                        color: congestion.color,
                        padding: '6px 12px',
                        borderRadius: '20px',
                        fontSize: '12px',
                        fontWeight: '700',
                        textTransform: 'uppercase'
                      }}>
                        {congestion.level}
                      </span>
                    </div>
                  </div>

                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                    gap: '16px',
                    padding: '16px',
                    backgroundColor: '#f8fafc',
                    borderRadius: '8px'
                  }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
                        {videoCount}
                      </div>
                      <div style={{ fontSize: '14px', color: '#666' }}>Videos</div>
                    </div>
                    
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
                        {totalVehicles}
                      </div>
                      <div style={{ fontSize: '14px', color: '#666' }}>Total Vehicles</div>
                    </div>
                    
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#8b5cf6' }}>
                        {videoCount > 0 ? Math.round(totalVehicles / videoCount) : 0}
                      </div>
                      <div style={{ fontSize: '14px', color: '#666' }}>Avg per Video</div>
                    </div>
                  </div>

                  <div style={{ 
                    marginTop: '16px', 
                    paddingTop: '16px', 
                    borderTop: '1px solid #e5e7eb',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <span style={{ fontSize: '14px', color: '#6b7280' }}>
                      Created: {group.created_at ? new Date(group.created_at).toLocaleDateString() : 'Unknown'}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        viewGroupDetail(group.id);
                      }}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid #3b82f6',
                        borderRadius: '6px',
                        backgroundColor: '#3b82f6',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '500'
                      }}
                    >
                      View Analysis
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default GroupAnalysis;