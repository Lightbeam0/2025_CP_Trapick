// src/pages/AnalysisResults.js
import React, { useState, useEffect } from "react";
import axios from "axios";
import ProcessedVideoViewer from "../components/ProcessedVideoViewer";

function AnalysisResults() {
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all"); // all, completed, processing, failed
  
  // Add date filter state
  const [dateFilter, setDateFilter] = useState('all');
  const [locationFilter, setLocationFilter] = useState('all');

  useEffect(() => {
    fetchAnalyses();
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
              ...video,
              analysis: analysisResponse.data.analysis || null,
              video_info: analysisResponse.data.video_info || null
            };
          } catch (error) {
            console.error(`Error fetching analysis for video ${video.id}:`, error);
            return { ...video, analysis: null, video_info: null };
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

  // Add filtering function
  const getFilteredAnalyses = () => {
    let filtered = analyses;
    
    // Filter by date
    if (dateFilter !== 'all') {
      filtered = filtered.filter(analysis => {
        const videoDate = analysis.video_date;
        if (!videoDate) return false;
        
        const today = new Date();
        const analysisDate = new Date(videoDate);
        
        switch (dateFilter) {
          case 'today':
            return analysisDate.toDateString() === today.toDateString();
          case 'week':
            const weekAgo = new Date(today.setDate(today.getDate() - 7));
            return analysisDate >= weekAgo;
          case 'month':
            const monthAgo = new Date(today.setMonth(today.getMonth() - 1));
            return analysisDate >= monthAgo;
          default:
            return true;
        }
      });
    }
    
    // Filter by location
    if (locationFilter !== 'all') {
      filtered = filtered.filter(analysis => 
        analysis.location && analysis.location.id === locationFilter
      );
    }
    
    return filtered;
  };

  const viewProcessedVideo = (videoId) => {
    setSelectedVideoId(videoId);
  };

  const deleteAnalysis = async (videoId, videoName) => {
    if (window.confirm(`Are you sure you want to delete the analysis for "${videoName}"?`)) {
      try {
        // CORRECTED ENDPOINT: Use the proper DELETE endpoint
        await axios.delete(`http://127.0.0.1:8000/api/videos/${videoId}/`);
        
        // Show success message
        alert('Analysis deleted successfully!');
        
        // Refresh the list
        fetchAnalyses();
      } catch (err) {
        console.error("Error deleting analysis:", err);
        alert("Error deleting analysis: " + (err.response?.data?.error || err.message));
      }
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      'completed': { color: '#10b981', text: 'Completed' },
      'processing': { color: '#f59e0b', text: 'Processing' },
      'failed': { color: '#ef4444', text: 'Failed' },
      'uploaded': { color: '#6b7280', text: 'Uploaded' }
    };
    
    const config = statusConfig[status] || statusConfig['uploaded'];
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

  if (selectedVideoId) {
    return (
      <ProcessedVideoViewer 
        videoId={selectedVideoId} 
        onClose={() => setSelectedVideoId(null)}
        onBack={() => setSelectedVideoId(null)}
      />
    );
  }

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Video Analysis Results
        </h1>
        <p style={{ color: '#666', margin: 0 }}>View and manage all processed traffic video analyses</p>
      </header>

      {/* Filters and Stats */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h3 style={{ margin: '0 0 8px 0' }}>Analysis Overview</h3>
            <p style={{ color: '#666', margin: 0, fontSize: '14px' }}>
              Total: {getFilteredAnalyses().length} analyses • 
              Completed: {getFilteredAnalyses().filter(a => a.processing_status === 'completed').length} • 
              Processing: {getFilteredAnalyses().filter(a => a.processing_status === 'processing').length}
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
                {/* Add other locations */}
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
                <option value="all">All Analyses</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
              </select>
            </div>
            
            <button 
              onClick={fetchAnalyses}
              style={{
                padding: '8px 16px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: 'white',
                cursor: 'pointer'
              }}
            >
              Refresh
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

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '18px', color: '#666' }}>Loading analyses...</div>
        </div>
      ) : getFilteredAnalyses().length === 0 ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>
            No analyses found
          </div>
          <p style={{ color: '#999' }}>
            {filter !== 'all' || dateFilter !== 'all' || locationFilter !== 'all' 
              ? 'No analyses match your filters.' 
              : 'Upload a video to see analysis results.'}
          </p>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Video Information</th>
                <th>Date & Time</th>
                <th>Analysis Results</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {getFilteredAnalyses().map((analysis) => (
                <tr key={analysis.id}>
                  <td>
                    <div>
                      <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                        {analysis.title || analysis.filename}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        Duration: {formatDuration(analysis.duration_seconds)}
                        {analysis.location && ` • ${analysis.location.display_name}`}
                      </div>
                    </div>
                  </td>
                  <td>
                    <div>
                      <div style={{ fontWeight: '500' }}>
                        {analysis.video_date_display || 'Unknown date'}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        {analysis.time_range || 'Time unknown'}
                      </div>
                    </div>
                  </td>
                  <td>
                    {analysis.analysis ? (
                      <div>
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontWeight: '600' }}>{analysis.analysis.total_vehicles} vehicles</span>
                          {analysis.analysis.congestion_level && (
                            getCongestionBadge(analysis.analysis.congestion_level)
                          )}
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                          Cars: {analysis.analysis.vehicle_breakdown?.cars || 0} • 
                          Trucks: {analysis.analysis.vehicle_breakdown?.trucks || 0} • 
                          Motorcycles: {analysis.analysis.vehicle_breakdown?.motorcycles || 0}
                        </div>
                      </div>
                    ) : analysis.processing_status === 'completed' ? (
                      <span style={{ color: '#999', fontSize: '14px' }}>No analysis data</span>
                    ) : (
                      <span style={{ color: '#999', fontSize: '14px' }}>Analysis in progress...</span>
                    )}
                  </td>
                  <td>
                    {getStatusBadge(analysis.processing_status)}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {analysis.processing_status === 'completed' && (
                        <button
                          onClick={() => viewProcessedVideo(analysis.id)}
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
                          View Video
                        </button>
                      )}
                      
                      <button
                        onClick={() => deleteAnalysis(analysis.id, analysis.filename)}
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
      {getFilteredAnalyses().length > 0 && (
        <div className="dashboard-card" style={{ marginTop: '24px' }}>
          <h3 style={{ marginBottom: '16px' }}>Analysis Statistics</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
                {getFilteredAnalyses().length}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Total Analyses</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
                {getFilteredAnalyses().filter(a => a.processing_status === 'completed').length}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Completed</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#f59e0b' }}>
                {getFilteredAnalyses().filter(a => a.processing_status === 'processing').length}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Processing</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>
                {getFilteredAnalyses().filter(a => a.processing_status === 'failed').length}
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