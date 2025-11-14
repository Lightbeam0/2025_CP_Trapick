// src/pages/LocationGroups.js - UPDATED WITH DATE FILTER
import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";

function LocationGroups() {
  const { locationId } = useParams();
  const navigate = useNavigate();
  const [location, setLocation] = useState(null);
  const [groups, setGroups] = useState([]);
  const [filteredGroups, setFilteredGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [debugMode, setDebugMode] = useState(false);

  // Date filter states
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  const fetchLocationData = async () => {
    try {
      setLoading(true);
      console.log(`🔄 Fetching data for location ID: ${locationId}`);

      if (!locationId) {
        throw new Error("No location ID provided");
      }

      // Build query parameters for date filtering
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      if (searchTerm) params.append('search', searchTerm.trim());
      params.append('location', locationId);

      const locationUrl = `http://127.0.0.1:8000/api/locations/${locationId}/`;
      console.log(`📡 Requesting location: ${locationUrl}`);
      const locationResponse = await axios.get(locationUrl);
      console.log("✅ Location response:", locationResponse.data);
      setLocation(locationResponse.data);

      // Fetch groups for this location with filters
      const groupsBaseUrl = `http://127.0.0.1:8000/api/location-groups/`;
      const groupsUrl = `${groupsBaseUrl}?${params}`;
      console.log(`📡 Requesting groups with filters: ${groupsUrl}`);

      const groupsResponse = await axios.get(groupsUrl);
      console.log("✅ Groups response:", groupsResponse.data);

      // Handle both array and paginated responses
      const groupsData = Array.isArray(groupsResponse.data)
        ? groupsResponse.data
        : (groupsResponse.data.results || []);

      setGroups(groupsData);
      setFilteredGroups(groupsData); // Initialize filtered groups
      setError(null);

    } catch (err) {
      console.error("❌ Error fetching location data:", err);
      handleFetchError(err);
    } finally {
      setLoading(false);
      console.log("🏁 Location data fetch completed");
    }
  };

  const handleFetchError = (err) => {
    let errorMessage = "Failed to load location groups";

    if (err.response) {
      console.error("❌ Server responded with:", {
        status: err.response.status,
        data: err.response.data,
        headers: err.response.headers
      });

      if (err.response.status === 404) {
        errorMessage = "Location not found. It may have been deleted.";
      } else if (err.response.status === 400) {
        errorMessage = "Invalid location ID format.";
      } else if (err.response.data?.error) {
        errorMessage = `Server error: ${err.response.data.error}`;
      } else if (err.response.data?.detail) {
        errorMessage = `Server error: ${err.response.data.detail}`;
      } else {
        errorMessage = `Server error (${err.response.status})`;
      }
    } else if (err.request) {
      console.error("❌ No response received (network error?):", err.request);
      errorMessage = "Network error: Could not reach the server. Is it running?";
    } else {
      console.error("❌ Unexpected error:", err.message);
      errorMessage = `Unexpected error: ${err.message}`;
    }

    setError(errorMessage);
  };

  // Apply all filters
  const handleApplyFilters = () => {
    fetchLocationData();
  };

  // Clear all filters
  const handleClearFilters = () => {
    setStartDate('');
    setEndDate('');
    setSearchTerm('');
    fetchLocationData();
  };

  // Quick date filters
  const applyQuickFilter = (days) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    
    setStartDate(start.toISOString().split('T')[0]);
    setEndDate(end.toISOString().split('T')[0]);
    
    // Auto-apply after setting dates
    setTimeout(() => {
      fetchLocationData();
    }, 100);
  };

  // 🔍 Debug: Check all groups in system
  const checkAllGroups = async () => {
    try {
      console.log("🔍 Fetching all groups for debug...");
      const response = await axios.get('http://127.0.0.1:8000/api/location-groups/');
      const allGroups = Array.isArray(response.data) ? response.data : response.data.results || [];
      console.log(`🔍 Found ${allGroups.length} total groups in system:`, allGroups);
      
      // Log groups for this location specifically
      const locationGroups = allGroups.filter(g => 
        g.location?.id?.toString() === locationId || 
        g.location?.toString() === locationId
      );
      console.log(`🔍 Groups matching location ${locationId}:`, locationGroups);
    } catch (err) {
      console.error("❌ Error checking debug endpoint:", err);
    }
  };

  const viewGroupVideos = (groupId) => {
    console.log(`🎬 Navigating to group: ${groupId}`);
    navigate(`/locations/${locationId}/groups/${groupId}`);
  };

  useEffect(() => {
    if (locationId) {
      fetchLocationData();
      checkAllGroups();
    } else {
      setLoading(false);
      setError("No location ID provided in URL");
    }
  }, [locationId]);

  // Calculate date range summary
  const getDateRangeSummary = () => {
    if (!startDate && !endDate) return 'All dates';
    
    const start = startDate ? new Date(startDate).toLocaleDateString() : 'any start';
    const end = endDate ? new Date(endDate).toLocaleDateString() : 'any end';
    
    return `${start} to ${end}`;
  };

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

  if (error) {
    return (
      <div className="main-content">
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <div style={{ color: '#ef4444', fontSize: '18px', marginBottom: '16px' }}>{error}</div>

          <div style={{ marginBottom: '24px' }}>
            <button
              onClick={() => navigate('/locations')}
              style={{
                padding: '10px 20px',
                border: '1px solid #3b82f6',
                borderRadius: '4px',
                backgroundColor: '#3b82f6',
                color: 'white',
                cursor: 'pointer',
                marginRight: '12px'
              }}
            >
              Back to Locations
            </button>

            <button
              onClick={() => fetchLocationData()}
              style={{
                padding: '10px 20px',
                border: '1px solid #6b7280',
                borderRadius: '4px',
                backgroundColor: 'white',
                color: '#6b7280',
                cursor: 'pointer'
              }}
            >
              Retry
            </button>
          </div>

          {/* Developer debug tip */}
          <div style={{
            fontSize: '12px',
            color: '#9ca3af',
            marginTop: '24px',
            textAlign: 'left',
            maxWidth: '600px',
            margin: '24px auto 0'
          }}>
            <p>💡 <strong>Debug Tip:</strong> Open browser console to see detailed API logs.</p>
            <p>🔧 To test API directly, run in console:</p>
            <code style={{
              display: 'block',
              backgroundColor: '#f3f4f6',
              padding: '8px',
              borderRadius: '4px',
              marginTop: '8px',
              whiteSpace: 'pre-wrap'
            }}>
              {`fetch("http://127.0.0.1:8000/api/locations/${locationId}/").then(r => r.json()).then(console.log)`}
            </code>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button
            onClick={() => navigate('/locations')}
            style={{
              padding: '8px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: 'white',
              cursor: 'pointer',
              marginBottom: '16px'
            }}
          >
            ← Back to Locations
          </button>
          
          {/* Debug toggle for developers */}
          <button
            onClick={() => setDebugMode(!debugMode)}
            style={{
              padding: '4px 8px',
              border: '1px solid #9ca3af',
              borderRadius: '4px',
              backgroundColor: debugMode ? '#f3f4f6' : 'white',
              color: '#6b7280',
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            {debugMode ? '(Debug ON)' : 'Debug'}
          </button>
        </div>

        <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          {location?.display_name || 'Unknown Location'} - Video Groups
        </h1>
        <p style={{ color: '#666', margin: 0 }}>
          Videos grouped by recording date at {location?.display_name || 'this location'}
        </p>

        {debugMode && location && (
          <div style={{
            marginTop: '12px',
            padding: '12px',
            backgroundColor: '#f0f9ff',
            border: '1px solid #bae6fd',
            borderRadius: '6px',
            fontSize: '12px'
          }}>
            <strong>Debug Info:</strong> Location ID: {location.id} | Groups loaded: {groups.length}
          </div>
        )}
      </div>

      {/* --- ENHANCED FILTERS SECTION --- */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '16px' }}>Filter Groups</h3>
        
        {/* Quick Date Filters */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>
            Quick Date Filters
          </label>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => applyQuickFilter(7)}
              style={{
                padding: '6px 12px',
                border: '1px solid #3b82f6',
                borderRadius: '4px',
                backgroundColor: 'white',
                color: '#3b82f6',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              Last 7 Days
            </button>
            <button
              onClick={() => applyQuickFilter(30)}
              style={{
                padding: '6px 12px',
                border: '1px solid #10b981',
                borderRadius: '4px',
                backgroundColor: 'white',
                color: '#10b981',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              Last 30 Days
            </button>
            <button
              onClick={() => applyQuickFilter(90)}
              style={{
                padding: '6px 12px',
                border: '1px solid #f59e0b',
                borderRadius: '4px',
                backgroundColor: 'white',
                color: '#f59e0b',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              Last 90 Days
            </button>
          </div>
        </div>

        {/* Date Range Filters */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>
              Start Date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                fontSize: '14px'
              }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>
              End Date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                fontSize: '14px'
              }}
            />
          </div>
        </div>

        {/* Search Filter */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>
            Search Groups
          </label>
          <input
            type="text"
            placeholder="Search by date, vehicle count, or video filename..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              fontSize: '14px'
            }}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleApplyFilters();
              }
            }}
          />
        </div>

        {/* Filter Actions */}
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button
            onClick={handleClearFilters}
            style={{
              padding: '8px 16px',
              border: '1px solid #6b7280',
              borderRadius: '4px',
              backgroundColor: 'white',
              color: '#6b7280',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Clear All
          </button>
          <button
            onClick={handleApplyFilters}
            style={{
              padding: '8px 16px',
              border: '1px solid #3b82f6',
              borderRadius: '4px',
              backgroundColor: '#3b82f6',
              color: 'white',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            Apply Filters
          </button>
        </div>

        {/* Active Filters Summary */}
        {(startDate || endDate || searchTerm) && (
          <div style={{
            marginTop: '16px',
            padding: '12px',
            backgroundColor: '#f0f9ff',
            borderRadius: '6px',
            border: '1px solid #bae6fd'
          }}>
            <div style={{ fontSize: '14px', color: '#0369a1' }}>
              <strong>Active Filters:</strong> {getDateRangeSummary()}
              {searchTerm && ` • Search: "${searchTerm}"`}
              {` • Showing ${groups.length} of ${groups.length} groups`}
            </div>
          </div>
        )}
      </div>
      {/* --- END ENHANCED FILTERS SECTION --- */}

      {groups.length === 0 ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div style={{ fontSize: '64px', marginBottom: '16px', color: '#d1d5db' }}>📅</div>
          <h3 style={{ marginBottom: '12px', color: '#374151' }}>No Video Groups Found</h3>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>
            {searchTerm || startDate || endDate 
              ? `No groups found matching your filters. Try adjusting your search criteria.`
              : "No processed videos found for this location yet."
            }
          </p>
          {(searchTerm || startDate || endDate) && (
            <button
              onClick={handleClearFilters}
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
              Clear Filters
            </button>
          )}
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <div>
              <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '600' }}>Date Groups</h2>
              <p style={{ color: '#666', margin: '4px 0 0 0', fontSize: '14px' }}>
                {groups.length} date groups • {groups.reduce((total, group) => total + (group.video_count || 0), 0)} total videos
                {(startDate || endDate || searchTerm) && (
                  <span style={{ color: '#3b82f6', marginLeft: '8px' }}>
                    (filtered results)
                  </span>
                )}
              </p>
            </div>
            
            {/* Export/Summary Actions */}
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{
                backgroundColor: '#f0f9ff',
                color: '#0369a1',
                padding: '4px 8px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: '500'
              }}>
                {getDateRangeSummary()}
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gap: '16px' }}>
            {groups.map(group => (
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
                onClick={() => viewGroupVideos(group.id)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                  <div style={{ flex: 1 }}>
                    <h3 style={{ margin: '0 0 8px 0', color: '#1f2937', fontSize: '20px' }}>
                      {new Date(group.date).toLocaleDateString('en-US', { 
                        weekday: 'long', 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric' 
                      })}
                    </h3>
                    
                    {group.time_range && group.time_range !== "No time data" && (
                      <p style={{ color: '#6b7280', margin: '0 0 8px 0', fontSize: '14px' }}>
                        🕒 {group.time_range}
                      </p>
                    )}
                  </div>
                  
                  <div style={{ textAlign: 'right' }}>
                    <span style={{
                      backgroundColor: '#3b82f6',
                      color: 'white',
                      padding: '6px 12px',
                      borderRadius: '20px',
                      fontSize: '14px',
                      fontWeight: '600'
                    }}>
                      {group.video_count || 0} videos
                    </span>
                  </div>
                </div>

                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
                  gap: '16px',
                  padding: '16px',
                  backgroundColor: '#f8fafc',
                  borderRadius: '8px'
                }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#10b981' }}>
                      {group.total_vehicles || 0}
                    </div>
                    <div style={{ fontSize: '14px', color: '#666' }}>Total Vehicles</div>
                  </div>
                  
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#8b5cf6' }}>
                      {group.video_count > 0 ? Math.round((group.total_vehicles || 0) / group.video_count) : 0}
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
                    Click to view {group.video_count || 0} videos
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      viewGroupVideos(group.id);
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
                    View Videos →
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default LocationGroups;