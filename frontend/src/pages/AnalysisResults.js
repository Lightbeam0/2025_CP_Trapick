// src/pages/AnalysisResults.js
import React, { useState, useEffect } from "react";
import axios from "axios";
import ProcessedVideoViewer from "../components/ProcessedVideoViewer"; // Import the viewer

function AnalysisResults() {
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState(null); // New state for selected session
  const [analyses, setAnalyses] = useState([]); // Holds individual video analyses
  const [sessions, setSessions] = useState([]); // Holds session analyses
  const [loading, setLoading] = useState(true);
  const [sessionsLoading, setSessionsLoading] = useState(false); // Separate loading state for sessions
  const [error, setError] = useState(null);
  const [sessionErrors, setSessionErrors] = useState({}); // Track errors per session
  const [filter, setFilter] = useState("all"); // all, completed, processing, failed

  // Add date filter state
  const [dateFilter, setDateFilter] = useState('all');
  const [locationFilter, setLocationFilter] = useState('all');

  // Fetch individual video analyses (existing logic)
  useEffect(() => {
    fetchAnalyses();
    fetchSessions(); // Fetch sessions too
  }, [filter]);

  const fetchAnalyses = async () => {
    try {
      setLoading(true);
      const response = await axios.get("http://127.0.0.1:8000/api/videos/");
      let videoData = response.data;

      // Filter videos based on selection
      if (filter !== "all") {
        videoData = videoData.filter(video => video.processing_status === filter);
      }

      // For each video, get its analysis data
      const analysesWithDetails = await Promise.all(
        videoData.map(async (video) => {
          try {
            const analysisResponse = await axios.get(`http://127.0.0.1:8000/api/analysis/${video.id}/`);
            return {
              type: 'video', // Add type identifier
              id: video.id,
              ...video,
              analysis: analysisResponse.data.analysis || null,
              video_info: analysisResponse.data.video_info || null
            };
          } catch (error) {
            console.error(`Error fetching analysis for video ${video.id}:`, error);
            return {
              type: 'video', // Add type identifier
              id: video.id,
              ...video,
              analysis: null,
              video_info: null,
              error: `Failed to load analysis: ${error.message}`
            };
          }
        })
      );

      setAnalyses(analysesWithDetails);
      setError(null);
    } catch (err) {
      console.error("Error fetching analyses:", err);
      setError("Failed to load analysis data");
    } finally {
      setLoading(false);
    }
  };

  // Updated fetchSessions function with optimizations
const fetchSessions = async () => {
  try {
    setSessionsLoading(true);
    setSessionErrors({});
    const response = await axios.get('http://127.0.0.1:8000/api/sessions/');
    let sessionData = response.data;

    // Filter sessions based on selection
    if (filter !== "all") {
      sessionData = sessionData.filter(session => {
        if (filter === 'completed') return session.status === 'completed';
        if (filter === 'processing') return session.status === 'processing';
        if (filter === 'failed') return session.status === 'failed';
        if (filter === 'uploaded') return session.status === 'pending_upload';
        return true;
      });
    }

    // For each session, get its aggregated analysis data if available
    const sessionsWithDetails = await Promise.all(
      sessionData.map(async (session) => {
        let aggregatedAnalysis = null;
        let sessionError = null;

        if (session.status === 'completed') {
          try {
            // Try multiple approaches to find the session analysis
            
            // Approach 1: Look for TrafficAnalysis with analysis_session matching session ID
            const sessionAnalysesResponse = await axios.get(`http://127.0.0.1:8000/api/sessions/${session.id}/traffic-analyses/`);
            const sessionAnalyses = sessionAnalysesResponse.data;
            
            if (sessionAnalyses && sessionAnalyses.length > 0) {
              // Use the first analysis found (should be the aggregated one)
              const sessionAnalysis = sessionAnalyses[0];
              
              // Extract analysis data from the TrafficAnalysis record
              aggregatedAnalysis = {
                total_vehicles: sessionAnalysis.total_vehicles || 0,
                vehicle_breakdown: sessionAnalysis.analysis_data?.summary?.vehicle_breakdown || {
                  cars: sessionAnalysis.car_count || 0,
                  trucks: sessionAnalysis.truck_count || 0,
                  motorcycles: sessionAnalysis.motorcycle_count || 0,
                  buses: sessionAnalysis.bus_count || 0,
                  bicycles: sessionAnalysis.bicycle_count || 0,
                  others: sessionAnalysis.other_count || 0
                },
                congestion_level: sessionAnalysis.congestion_level || 'low',
                traffic_pattern: sessionAnalysis.traffic_pattern || 'stable'
              };
              
              console.log(`✅ Found session analysis for session ${session.id}:`, aggregatedAnalysis);
            } else {
              // Approach 2: Check if there's analysis data in the session itself
              if (session.analysis_data) {
                aggregatedAnalysis = {
                  total_vehicles: session.analysis_data.summary?.total_vehicles_counted || 0,
                  vehicle_breakdown: session.analysis_data.summary?.vehicle_breakdown || {},
                  congestion_level: session.analysis_data.metrics?.congestion_level || 'low',
                  traffic_pattern: session.analysis_data.metrics?.traffic_pattern || 'stable'
                };
                console.log(`✅ Using session-level analysis data for ${session.id}`);
              } else {
                sessionError = "No analysis data found for completed session";
                console.warn(`❌ No analysis data found for completed session ${session.id}`);
              }
            }
          } catch (error) {
            console.error(`Error fetching analysis for session ${session.id}:`, error);
            sessionError = `Failed to load analysis data: ${error.message}`;
          }
        }

        // Track session errors
        if (sessionError) {
          setSessionErrors(prev => ({
            ...prev,
            [session.id]: sessionError
          }));
        }

        return {
          type: 'session',
          id: session.id,
          ...session,
          analysis: aggregatedAnalysis,
          video_info: null,
          error: sessionError
        };
      })
    );

    setSessions(sessionsWithDetails);
  } catch (err) {
    console.error("Error fetching sessions:", err);
    setError("Failed to load session data");
  } finally {
    setSessionsLoading(false);
  }
};

  // Combine and filter analyses and sessions
  const getCombinedResults = () => {
    let combined = [...analyses, ...sessions];

    // Filter by date
    if (dateFilter !== 'all') {
      const today = new Date();
      combined = combined.filter(item => {
        let dateToCheck;
        if (item.type === 'video') {
            dateToCheck = item.video_date;
        } else { // item.type === 'session'
            dateToCheck = item.start_datetime; // Use session start date
        }
        if (!dateToCheck) return false;

        const itemDate = new Date(dateToCheck);

        switch (dateFilter) {
          case 'today':
            return itemDate.toDateString() === today.toDateString();
          case 'week':
            const weekAgo = new Date(today); // Create new Date object to avoid mutation
            weekAgo.setDate(weekAgo.getDate() - 7);
            return itemDate >= weekAgo;
          case 'month':
            const monthAgo = new Date(today); // Create new Date object to avoid mutation
            monthAgo.setMonth(monthAgo.getMonth() - 1);
            return itemDate >= monthAgo;
          default:
            return true;
        }
      });
    }

    // Filter by location
    if (locationFilter !== 'all') {
      combined = combined.filter(item =>
        (item.type === 'video' && item.location && item.location.id === locationFilter) ||
        (item.type === 'session' && item.location && item.location === locationFilter) // Assuming location is ID in session
      );
    }

    // Sort by date/time (descending)
    combined.sort((a, b) => {
        const dateA = a.type === 'video' ? new Date(a.video_date || a.uploaded_at) : new Date(a.start_datetime);
        const dateB = b.type === 'video' ? new Date(b.video_date || b.uploaded_at) : new Date(b.start_datetime);
        return dateB - dateA; // Descending order
    });

    return combined;
  };

  // View functions - update to handle type
  const viewProcessedVideo = (itemId, itemType) => { // Accept type
    if (itemType === 'session') {
        setSelectedSessionId(itemId); // Set session ID
        setSelectedVideoId(null);    // Clear video ID
    } else { // itemType === 'video'
        setSelectedVideoId(itemId);  // Set video ID
        setSelectedSessionId(null);  // Clear session ID
    }
  };

  const deleteAnalysis = async (itemId, itemType, itemName) => { // Accept type
    let endpoint, successMessage, errorMessage;
    if (itemType === 'session') {
        endpoint = `http://127.0.0.1:8000/api/sessions/${itemId}/`;
        successMessage = 'Analysis session deleted successfully!';
        errorMessage = 'Error deleting analysis session';
    } else { // itemType === 'video'
        endpoint = `http://127.0.0.1:8000/api/videos/${itemId}/`;
        successMessage = 'Analysis deleted successfully!';
        errorMessage = 'Error deleting analysis';
    }

    if (window.confirm(`Are you sure you want to delete the ${itemType} "${itemName}"?`)) {
      try {
        await axios.delete(endpoint);
        alert(successMessage);
        // Refresh the list
        if (itemType === 'session') {
            fetchSessions(); // Refresh sessions
        } else {
            fetchAnalyses(); // Refresh videos
        }
      } catch (err) {
        console.error(`${errorMessage}:`, err);
        alert(`${errorMessage}: ${err.response?.data?.error || err.message}`);
      }
    }
  };

  const getStatusBadge = (status, type) => { // Accept type to maybe customize session statuses
    const statusConfig = {
      'completed': { color: '#10b981', text: 'Completed' },
      'processing': { color: '#f59e0b', text: 'Processing' },
      'failed': { color: '#ef4444', text: 'Failed' },
      'pending_upload': { color: '#6b7280', text: 'Pending Upload' } // Add session status
    };

    const config = statusConfig[status] || { color: '#6b7280', text: status };
    return (
      <span style={{
        backgroundColor: config.color + '20',
        color: config.color,
        padding: '4px 8px',
        borderRadius: '12px',
        fontSize: '12px',
        fontWeight: '600'
      }}>
        {config.text}
      </span>
    );
  };

  const getCongestionBadge = (level) => {
    const levelConfig = {
      'high': { color: '#ef4444', text: 'High' },
      'medium': { color: '#f59e0b', text: 'Medium' },
      'low': { color: '#10b981', text: 'Low' },
      'very_low': { color: '#6b7280', text: 'Very Low' },
      'severe': { color: '#dc2626', text: 'Severe' }
    };

    const config = levelConfig[level] || levelConfig['low'];
    return (
      <span style={{
        backgroundColor: config.color + '20',
        color: config.color,
        padding: '2px 6px',
        borderRadius: '8px',
        fontSize: '10px',
        fontWeight: '500'
      }}>
        {config.text}
      </span>
    );
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return 'Unknown';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'Unknown';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // NEW: Check which viewer to render
  if (selectedVideoId) {
    return (
      <ProcessedVideoViewer
        videoId={selectedVideoId}
        type="video" // Pass type
        onClose={() => setSelectedVideoId(null)}
        onBack={() => setSelectedVideoId(null)}
      />
    );
  }

  if (selectedSessionId) { // Render viewer for session
    return (
      <ProcessedVideoViewer
        videoId={selectedSessionId} // Pass session ID here
        type="session" // Pass type
        onClose={() => setSelectedSessionId(null)}
        onBack={() => setSelectedSessionId(null)}
      />
    );
  }

  // Combine and filter results for display
  const combinedResults = getCombinedResults();
  const isLoading = loading || sessionsLoading;

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Video & Session Analysis Results
        </h1>
        <p style={{ color: '#666', margin: 0 }}>View and manage all processed traffic video analyses and sessions</p>
      </header>

      {/* Filters and Stats */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h3 style={{ margin: '0 0 8px 0' }}>Analysis Overview</h3>
            <p style={{ color: '#666', margin: 0, fontSize: '14px' }}>
              Total: {combinedResults.length} items •
              Videos: {analyses.length} •
              Sessions: {sessions.length} •
              Completed: {combinedResults.filter(a => a.status === 'completed' || a.processing_status === 'completed').length}
              {sessionsLoading && " • (Loading sessions...)"}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <label style={{ fontSize: '14px', fontWeight: '500', marginRight: '8px' }}>Date:</label>
              <select
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
                className="select-input"
              >
                <option value="all">All Dates</option>
                <option value="today">Today</option>
                <option value="week">Past Week</option>
                <option value="month">Past Month</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '14px', fontWeight: '500', marginRight: '8px' }}>Location:</label>
              <select
                value={locationFilter}
                onChange={(e) => setLocationFilter(e.target.value)}
                className="select-input"
              >
                <option value="all">All Locations</option>
                <option value="1">Baliwasan Area</option>
                <option value="2">San Roque</option>
                {/* Add other locations dynamically if needed */}
              </select>
            </div>

            <div>
              <label style={{ fontSize: '14px', fontWeight: '500', marginRight: '8px' }}>Status:</label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="select-input"
                style={{ minWidth: '120px' }}
              >
                <option value="all">All Analyses/Sessions</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
                <option value="uploaded">Pending Upload (Sessions)</option>
              </select>
            </div>

            <button
              onClick={() => { fetchAnalyses(); fetchSessions(); }} // Refresh both
              disabled={isLoading}
              style={{
                padding: '8px 16px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: 'white',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                opacity: isLoading ? 0.6 : 1
              }}
            >
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div style={{
          backgroundColor: '#fee2e2',
          border: '1px solid #fecaca',
          color: '#dc2626',
          padding: '12px 16px',
          borderRadius: '4px',
          marginBottom: '24px'
        }}>
          {error}
        </div>
      )}

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '18px', color: '#666' }}>
            {loading && sessionsLoading 
              ? "Loading analyses and sessions..." 
              : loading 
                ? "Loading video analyses..." 
                : "Loading sessions..."}
          </div>
        </div>
      ) : combinedResults.length === 0 ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>
            No analyses or sessions found
          </div>
          <p style={{ color: '#999' }}>
            {filter !== 'all' || dateFilter !== 'all' || locationFilter !== 'all'
              ? 'No items match your filters.'
              : 'Upload a video or create a session to see analysis results.'}
          </p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Type & Information</th>
                <th>Date & Time</th>
                <th>Analysis Results</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {combinedResults.map((item) => (
                <tr key={`${item.type}-${item.id}`}>
                  <td>
                    <div>
                      <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                        {/* Distinguish type visually */}
                        {item.type === 'session' ? '[SESSION] ' : '[VIDEO] '}
                        {item.type === 'session' ? item.name : (item.title || item.filename)}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        {/* Show relevant info based on type */}
                        {item.type === 'session' ? (
                          <>
                            {item.location_details?.display_name || `Loc ID: ${item.location}`} •
                            {item.video_files_count} videos
                          </>
                        ) : (
                          <>
                            Duration: {formatDuration(item.duration_seconds)} •
                            {item.location && ` ${item.location.display_name}`}
                          </>
                        )}
                      </div>
                    </div>
                  </td>
                  <td>
                    <div>
                      <div style={{ fontWeight: '500' }}>
                        {item.type === 'session' ?
                          `${new Date(item.start_datetime).toLocaleDateString('en-US', { timeZone: 'UTC' })} to ${new Date(item.end_datetime).toLocaleDateString('en-US', { timeZone: 'UTC' })}` :
                          (item.video_date_display || 'Unknown date')
                        }
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        {item.type === 'session' ? `Status: ${item.status}` : (item.time_range || 'Time unknown')}
                      </div>
                    </div>
                  </td>
                  <td>
                    {item.error ? (
                      <span style={{ color: '#ef4444', fontSize: '12px' }}>
                        Error: {item.error}
                      </span>
                    ) : item.analysis ? (
                      <div>
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontWeight: '600' }}>{item.analysis.total_vehicles} vehicles</span>
                          {item.analysis.congestion_level && (
                            getCongestionBadge(item.analysis.congestion_level)
                          )}
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                          Cars: {item.analysis.vehicle_breakdown?.cars || 0} •
                          Trucks: {item.analysis.vehicle_breakdown?.trucks || 0} •
                          Motorcycles: {item.analysis.vehicle_breakdown?.motorcycles || 0}
                        </div>
                      </div>
                    ) : item.status === 'completed' || item.processing_status === 'completed' ? (
                      <span style={{ color: '#999', fontSize: '14px' }}>No analysis data</span>
                    ) : (
                      <span style={{ color: '#999', fontSize: '14px' }}>Analysis in progress...</span>
                    )}
                  </td>
                  <td>
                    {getStatusBadge(item.status || item.processing_status, item.type)}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {(item.status === 'completed' || item.processing_status === 'completed') && (
                        <button
                          onClick={() => viewProcessedVideo(item.id, item.type)}
                          style={{
                            padding: '6px 12px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: '#3b82f6',
                            color: 'white',
                            fontSize: '12px',
                            cursor: 'pointer'
                          }}
                        >
                          View {item.type === 'session' ? 'Session' : 'Video'}
                        </button>
                      )}

                      <button
                        onClick={() => deleteAnalysis(item.id, item.type, item.type === 'session' ? item.name : item.filename)}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid #ef4444',
                          borderRadius: '4px',
                          backgroundColor: 'white',
                          color: '#ef4444',
                          fontSize: '12px',
                          cursor: 'pointer'
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Analysis Statistics */}
      {combinedResults.length > 0 && (
        <div className="dashboard-card" style={{ marginTop: '24px' }}>
          <h3 style={{ marginBottom: '16px' }}>Analysis Statistics</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
                {combinedResults.length}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Total Items</div>
            </div>

            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
                {combinedResults.filter(a => a.status === 'completed' || a.processing_status === 'completed').length}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Completed</div>
            </div>

            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#f59e0b' }}>
                {combinedResults.filter(a => a.status === 'processing' || a.processing_status === 'processing').length}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Processing</div>
            </div>

            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>
                {combinedResults.filter(a => a.status === 'failed' || a.processing_status === 'failed').length}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Failed</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AnalysisResults;