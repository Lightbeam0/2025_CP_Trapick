// src/pages/AnalysisResults.js - UPDATED FOR NEW APPROACH
import React, { useState, useEffect } from "react";
import axios from "axios";
import ProcessedVideoViewer from "../components/ProcessedVideoViewer";

function AnalysisResults() {
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [videos, setVideos] = useState([]);
  const [locationGroups, setLocationGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState('all');
  const [locationFilter, setLocationFilter] = useState('all');
  const [locations, setLocations] = useState([]);
  const [ungroupedVideos, setUngroupedVideos] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);

  useEffect(() => {
    fetchVideos();
    fetchLocationGroups();
    fetchLocations();
    fetchUngroupedVideos();
  }, [filter, dateFilter, locationFilter]);

  const fetchVideos = async () => {
    try {
      setLoading(true);
      const response = await axios.get("http://127.0.0.1:8000/api/videos/");
      
      let videoData = response.data;
      
      // Filter videos based on selection
      if (filter !== "all") {
        videoData = videoData.filter(video => video.processing_status === filter);
      }

      // For each video, get its analysis data
      const videosWithDetails = await Promise.all(
        videoData.map(async (video) => {
          try {
            const analysisResponse = await axios.get(`http://127.0.0.1:8000/api/analysis/${video.id}/`);
            return {
              type: 'video',
              id: video.id,
              ...video,
              analysis: analysisResponse.data.analysis || null,
              video_info: analysisResponse.data.video_info || null
            };
          } catch (error) {
            console.error(`Error fetching analysis for video ${video.id}:`, error);
            return {
              type: 'video',
              id: video.id,
              ...video,
              analysis: null,
              video_info: null,
              error: `Failed to load analysis: ${error.message}`
            };
          }
        })
      );

      setVideos(videosWithDetails);
      setError(null);
    } catch (err) {
      console.error("Error fetching videos:", err);
      setError("Failed to load video data");
    } finally {
      setLoading(false);
    }
  };

  const fetchLocationGroups = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/location-groups/");
      setLocationGroups(response.data);
    } catch (err) {
      console.error("Error fetching location groups:", err);
    }
  };

  const fetchLocations = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/locations/");
      setLocations(response.data);
    } catch (err) {
      console.error("Error fetching locations:", err);
    }
  };

  const fetchUngroupedVideos = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/videos/ungrouped/");
      setUngroupedVideos(response.data);
    } catch (err) {
      console.error("Error fetching ungrouped videos:", err);
    }
  };

  const getCombinedResults = () => {
    let combined = [...videos];

    // Filter by status
    if (filter !== "all") {
      combined = combined.filter(item => item.processing_status === filter);
    }

    // Filter by date
    if (dateFilter !== 'all') {
      const today = new Date();
      combined = combined.filter(item => {
        let itemDate = item.video_date ? new Date(item.video_date) : new Date(item.uploaded_at);
        
        switch (dateFilter) {
          case 'today':
            return itemDate.toDateString() === today.toDateString();
          case 'week':
            const weekAgo = new Date();
            weekAgo.setDate(weekAgo.getDate() - 7);
            return itemDate >= weekAgo;
          case 'month':
            const monthAgo = new Date();
            monthAgo.setMonth(monthAgo.getMonth() - 1);
            return itemDate >= monthAgo;
          default:
            return true;
        }
      });
    }

    // Filter by location
    if (locationFilter !== 'all') {
      combined = combined.filter(item => {
        return item.location && item.location.id.toString() === locationFilter;
      });
    }

    // Sort by date/time (descending)
    combined.sort((a, b) => {
      const getDate = (item) => {
        return item.video_date ? new Date(item.video_date) : new Date(item.uploaded_at);
      };
      
      return getDate(b) - getDate(a);
    });

    return combined;
  };

  const viewProcessedVideo = (videoId) => {
    setSelectedVideoId(videoId);
  };

  const deleteVideo = async (videoId, videoName) => {
    try {
      if (!window.confirm(`Are you sure you want to delete the video "${videoName}"?`)) {
        return;
      }

      await axios.delete(`http://127.0.0.1:8000/api/videos/${videoId}/`);
      alert('Video deleted successfully!');
      fetchVideos();
      fetchUngroupedVideos();
      
    } catch (err) {
      console.error('Error deleting video:', err);
      alert(`Error deleting video: ${err.response?.data?.error || err.message}`);
    }
  };

  const updateVideoMetadata = async (videoId, updates) => {
    try {
      await axios.put(`http://127.0.0.1:8000/api/videos/${videoId}/manage/`, updates);
      alert('Video metadata updated successfully!');
      fetchVideos();
      fetchUngroupedVideos();
    } catch (err) {
      console.error('Error updating video metadata:', err);
      alert(`Error updating video: ${err.response?.data?.error || err.message}`);
    }
  };

  const addVideosToGroup = async (group, videoIds) => {
    try {
      await axios.post(`http://127.0.0.1:8000/api/location-groups/${group.id}/videos/`, {
        video_ids: videoIds
      });
      alert(`Added ${videoIds.length} videos to ${group.location_details.display_name} - ${group.date}`);
      fetchVideos();
      fetchUngroupedVideos();
      fetchLocationGroups();
    } catch (err) {
      console.error('Error adding videos to group:', err);
      alert(`Error adding videos to group: ${err.response?.data?.error || err.message}`);
    }
  };

  const removeVideosFromGroup = async (group, videoIds) => {
    try {
      await axios.delete(`http://127.0.0.1:8000/api/location-groups/${group.id}/videos/`, {
        data: { video_ids: videoIds }
      });
      alert(`Removed ${videoIds.length} videos from ${group.location_details.display_name} - ${group.date}`);
      fetchVideos();
      fetchUngroupedVideos();
      fetchLocationGroups();
    } catch (err) {
      console.error('Error removing videos from group:', err);
      alert(`Error removing videos from group: ${err.response?.data?.error || err.message}`);
    }
  };

  const createLocationGroup = async (locationId, date) => {
    try {
      await axios.post('http://127.0.0.1:8000/api/location-groups/', {
        location: locationId,
        date: date
      });
      alert('Location group created successfully!');
      fetchLocationGroups();
    } catch (err) {
      console.error('Error creating location group:', err);
      alert(`Error creating group: ${err.response?.data?.error || err.message}`);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      'completed': { color: '#10b981', text: 'Completed' },
      'processing': { color: '#f59e0b', text: 'Processing' },
      'failed': { color: '#ef4444', text: 'Failed' },
      'pending': { color: '#6b7280', text: 'Pending' }
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

  // Show video viewer when a video is selected
  if (selectedVideoId) {
    return (
      <ProcessedVideoViewer
        videoId={selectedVideoId}
        type="video"
        onClose={() => setSelectedVideoId(null)}
        onBack={() => setSelectedVideoId(null)}
      />
    );
  }

  const combinedResults = getCombinedResults();

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
              Total Videos: {combinedResults.length} •
              Completed: {combinedResults.filter(v => v.processing_status === 'completed').length} •
              Ungrouped: {ungroupedVideos.length} •
              Location Groups: {locationGroups.length}
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
                {locations.map(loc => (
                  <option key={loc.id} value={loc.id}>{loc.display_name}</option>
                ))}
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
                <option value="all">All Videos</option>
                <option value="completed">Completed</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            <button
              onClick={() => { fetchVideos(); fetchLocationGroups(); fetchUngroupedVideos(); }}
              disabled={loading}
              style={{
                padding: '8px 16px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: 'white',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.6 : 1
              }}
            >
              {loading ? 'Refreshing...' : 'Refresh'}
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

      {/* Quick Actions */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '16px' }}>Quick Actions</h3>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            onClick={() => {
              const location = prompt("Enter location ID:");
              const date = prompt("Enter date (YYYY-MM-DD):");
              if (location && date) {
                createLocationGroup(location, date);
              }
            }}
            style={{
              padding: '8px 16px',
              border: '1px solid #10b981',
              borderRadius: '4px',
              backgroundColor: '#f0fff4',
              color: '#065f46',
              cursor: 'pointer'
            }}
          >
            + Create Location Group
          </button>
          
          {ungroupedVideos.length > 0 && (
            <span style={{ color: '#666', fontSize: '14px', display: 'flex', alignItems: 'center' }}>
              {ungroupedVideos.length} videos available for grouping
            </span>
          )}
        </div>
      </div>

      {/* Location Groups */}
      {locationGroups.length > 0 && (
        <div className="dashboard-card" style={{ marginBottom: '24px' }}>
          <h3 style={{ marginBottom: '16px' }}>Location-Date Groups</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
            {locationGroups.map(group => (
              <div key={group.id} style={{
                padding: '16px',
                backgroundColor: '#f8fafc',
                borderRadius: '8px',
                border: '1px solid #e5e7eb'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                  <div>
                    <h4 style={{ fontWeight: '600', marginBottom: '4px' }}>
                      {group.location_details?.display_name || 'Unknown Location'}
                    </h4>
                    <p style={{ color: '#666', fontSize: '14px' }}>{group.date}</p>
                  </div>
                  <span style={{
                    backgroundColor: '#3b82f6',
                    color: 'white',
                    padding: '4px 8px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    fontWeight: '500'
                  }}>
                    {group.video_count} videos
                  </span>
                </div>
                
                <div style={{ fontSize: '14px', color: '#666', marginBottom: '12px' }}>
                  Total Vehicles: {group.total_vehicles || 0}
                </div>
                
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    onClick={() => {
                      const videoIds = ungroupedVideos.map(v => v.id);
                      if (videoIds.length > 0) {
                        addVideosToGroup(group, videoIds.slice(0, 3)); // Add first 3 for demo
                      }
                    }}
                    disabled={ungroupedVideos.length === 0}
                    style={{
                      padding: '6px 12px',
                      border: '1px solid #10b981',
                      borderRadius: '4px',
                      backgroundColor: ungroupedVideos.length === 0 ? '#f3f4f6' : '#f0fff4',
                      color: ungroupedVideos.length === 0 ? '#9ca3af' : '#065f46',
                      cursor: ungroupedVideos.length === 0 ? 'not-allowed' : 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    Add Videos
                  </button>
                  
                  <button
                    onClick={() => {
                      // View group analysis
                      window.open(`#group-${group.id}`, '_blank');
                    }}
                    style={{
                      padding: '6px 12px',
                      border: '1px solid #3b82f6',
                      borderRadius: '4px',
                      backgroundColor: '#f0f9ff',
                      color: '#1e40af',
                      cursor: 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    View Analysis
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Videos Table */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '18px', color: '#666' }}>Loading video analyses...</div>
        </div>
      ) : combinedResults.length === 0 ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '40px' }}>
          <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>
            No videos found
          </div>
          <p style={{ color: '#999' }}>
            {filter !== 'all' || dateFilter !== 'all' || locationFilter !== 'all'
              ? 'No videos match your filters.'
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
                <th>Group</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {combinedResults.map((video) => (
                <tr key={video.id}>
                  <td>
                    <div>
                      <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                        {video.title || video.filename}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        Duration: {video.duration_seconds ? `${Math.round(video.duration_seconds / 60)}min` : 'Unknown'} •
                        {video.location && ` ${video.location.display_name}`}
                      </div>
                    </div>
                  </td>
                  <td>
                    <div>
                      <div style={{ fontWeight: '500' }}>
                        {video.video_date_display || 'Unknown date'}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        {video.time_range || 'Time unknown'}
                      </div>
                    </div>
                  </td>
                  <td>
                    {video.error ? (
                      <span style={{ color: '#ef4444', fontSize: '12px' }}>
                        Error: {video.error}
                      </span>
                    ) : video.analysis ? (
                      <div>
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontWeight: '600' }}>{video.analysis.total_vehicles} vehicles</span>
                          {video.analysis.congestion_level && (
                            getCongestionBadge(video.analysis.congestion_level)
                          )}
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                          Cars: {video.analysis.vehicle_breakdown?.cars || 0} •
                          Trucks: {video.analysis.vehicle_breakdown?.trucks || 0} •
                          Motorcycles: {video.analysis.vehicle_breakdown?.motorcycles || 0}
                        </div>
                      </div>
                    ) : video.processing_status === 'completed' ? (
                      <span style={{ color: '#999', fontSize: '14px' }}>No analysis data</span>
                    ) : (
                      <span style={{ color: '#999', fontSize: '14px' }}>Analysis in progress...</span>
                    )}
                  </td>
                  <td>
                    {getStatusBadge(video.processing_status)}
                  </td>
                  <td>
                    {video.location_date_group ? (
                      <span style={{ fontSize: '12px', color: '#666' }}>
                        {video.location_date_group.location_details?.display_name} - {video.location_date_group.date}
                      </span>
                    ) : (
                      <span style={{ fontSize: '12px', color: '#999' }}>Ungrouped</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                      {video.processing_status === 'completed' && (
                        <button
                          onClick={() => viewProcessedVideo(video.id)}
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
                        onClick={() => {
                          const newDate = prompt("Enter new date (YYYY-MM-DD):", video.video_date);
                          const newLocation = prompt("Enter new location ID:", video.location?.id);
                          if (newDate || newLocation) {
                            updateVideoMetadata(video.id, {
                              video_date: newDate,
                              location_id: newLocation
                            });
                          }
                        }}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid #f59e0b',
                          borderRadius: '4px',
                          backgroundColor: 'white',
                          color: '#f59e0b',
                          fontSize: '12px',
                          cursor: 'pointer'
                        }}
                      >
                        Edit
                      </button>

                      <button
                        onClick={() => deleteVideo(video.id, video.title || video.filename)}
                        disabled={video.processing_status === 'processing'}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid #ef4444',
                          borderRadius: '4px',
                          backgroundColor: video.processing_status === 'processing' ? '#f3f4f6' : 'white',
                          color: video.processing_status === 'processing' ? '#9ca3af' : '#ef4444',
                          fontSize: '12px',
                          cursor: video.processing_status === 'processing' ? 'not-allowed' : 'pointer'
                        }}
                        title={video.processing_status === 'processing' ? 'Stop processing first' : 'Delete video'}
                      >
                        {video.processing_status === 'processing' ? '⏳' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default AnalysisResults;