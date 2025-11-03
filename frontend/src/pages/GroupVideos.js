// src/pages/GroupVideos.js
import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import ProcessedVideoViewer from "../components/ProcessedVideoViewer";
import EditVideoModal from "../components/EditVideoModal";

// Helper functions defined outside component to avoid ESLint issues
const formatVideoTime = (time) => {
  if (!time) return 'Unknown';

  // If it's a string, handle different formats
  if (typeof time === 'string') {
    // Handle empty string
    if (time.trim() === '') return 'Unknown';

    // Handle HH:MM:SS format (e.g., "04:59:59")
    if (time.match(/^\d{1,2}:\d{2}:\d{2}$/)) {
      return time.substring(0, 5); // Return HH:MM
    }

    // Handle HH:MM format (e.g., "04:59")
    if (time.match(/^\d{1,2}:\d{2}$/)) {
      return time;
    }

    // Handle ISO format with T (e.g., "2023-01-01T04:59:59Z")
    if (time.includes('T')) {
      const timePart = time.split('T')[1];
      return timePart.substring(0, 5); // Get HH:MM
    }

    // If it's some other string format, try to extract time
    const timeMatch = time.match(/(\d{1,2}:\d{2})/);
    if (timeMatch) {
      return timeMatch[1];
    }

    return 'Unknown';
  }

  // If it's a time object with strftime method (from Django) - unlikely for DRF
  // If it's a time object serialized by DRF, it's usually a string like "HH:MM:SS" or "HH:MM"
  // The string handling above should cover it.

  return 'Unknown';
};

const formatDuration = (seconds) => {
  if (!seconds || seconds <= 0) return '';

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return ` • ${minutes} minutes`;
  } else {
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    if (remainingMinutes === 0) {
      return ` • ${hours} hour${hours > 1 ? 's' : ''}`;
    }
    return ` • ${hours}h ${remainingMinutes}m`;
  }
};

// Helper function to format location name
const formatLocationName = (location) => {
  if (!location) return 'Unknown Location';

  if (typeof location === 'string') {
    return location;
  }

  if (location.display_name) {
    return location.display_name;
  }

  if (location.name) {
    return location.name;
  }

  return 'Unknown Location';
};

function GroupVideos() {
  const { locationId, groupId } = useParams();
  const navigate = useNavigate();
  const [groupData, setGroupData] = useState(null);
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [editingVideo, setEditingVideo] = useState(null);
  const [locations, setLocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [pendingVideos, setPendingVideos] = useState([]);

  const fetchGroupData = useCallback(async () => {
    if (!locationId || !groupId) return;

    try {
      setLoading(true);
      console.log(`🔄 Fetching videos for location ${locationId}, group ${groupId}`);

      // ✅ FIXED: Use the correct URL pattern with location_id and group_id
      const response = await axios.get(
        `http://127.0.0.1:8000/api/locations/${locationId}/groups/${groupId}/videos/`
      );

      // ✅ ADD DIAGNOSTIC LOGGING
      console.log("🔍 FULL API RESPONSE:", response);
      console.log("🔍 Response data:", response.data);
      console.log("🔍 Group data:", response.data.group);
      console.log("🔍 Videos data:", response.data.videos);
      console.log("🔍 Videos count:", response.data.videos?.length);

      // ✅ Check if videos have processed_video_path
      if (response.data.videos) {
        response.data.videos.forEach((video, index) => {
          console.log(`🎬 Video ${index}:`, {
            id: video.id,
            filename: video.filename,
            title: video.title,
            start_time: video.start_time, // This is now the key field
            end_time: video.end_time,     // This is now the key field
            duration: video.duration,
            vehicle_count: video.vehicle_count,
            processed_video_path: video.processed_video_path,
            processing_status: video.processing_status,
            has_analysis: video.has_analysis
          });
        });
      }

      setGroupData(response.data);
      setError(null);
    } catch (err) {
      console.error("❌ Error fetching group videos:", err);
      console.error("❌ Error details:", {
        status: err.response?.status,
        data: err.response?.data,
        url: err.config?.url
      });

      if (err.response?.status === 404) {
        setError("Group not found or doesn't belong to this location");
      } else if (err.response?.status === 405) {
        setError("Method not allowed - please check the API endpoint");
      } else if (err.response?.data?.error) {
        setError(`Server error: ${err.response.data.error}`);
      } else {
        setError(`Failed to load group videos: ${err.message}`); // Fixed string interpolation
      }
    } finally {
      setLoading(false);
    }
  }, [locationId, groupId]);

  const fetchLocations = useCallback(async () => {
    try {
      console.log("🔄 Fetching locations for edit modal...");
      const response = await axios.get("http://127.0.0.1:8000/api/locations/");
      setLocations(response.data);
      console.log(`✅ Loaded ${response.data.length} locations for editing`);
    } catch (err) {
      console.error("❌ Error fetching locations:", err);
    }
  }, []);

  // ✅ ADD: Check for pending videos
  const checkForPendingVideos = useCallback(async () => {
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/videos/');
      const processing = response.data.filter(v =>
        v.processing_status === 'processing' || v.processing_status === 'uploaded'
      );

      setPendingVideos(processing);

      // If there are processing videos, enable polling
      if (processing.length > 0) {
        setIsPolling(true);
      } else {
        setIsPolling(false);
      }
    } catch (err) {
      console.error("Error checking pending videos:", err);
    }
  }, []);

  const viewVideoAnalysis = useCallback((videoId) => {
    console.log(`🎬 Viewing analysis for video ${videoId}`);
    setSelectedVideoId(videoId);
  }, []);

  const handleEditVideo = useCallback((video) => {
    console.log(`✏️ Opening edit modal for video ${video.id}:`, video);
    setEditingVideo(video);
  }, []);

  const handleVideoUpdated = useCallback((updatedVideo) => {
    console.log("✅ Video update callback received:", updatedVideo);
    setEditingVideo(null);
    // Refresh data whether updated or deleted
    fetchGroupData();
  }, [fetchGroupData]);

  // ✅ ADD: Auto-refresh polling effect
  useEffect(() => {
    if (!isPolling) return;

    const pollInterval = setInterval(() => {
      console.log("🔄 Auto-refreshing group videos...");
      fetchGroupData();
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(pollInterval);
  }, [isPolling, fetchGroupData]);

  // ✅ ADD: Enable polling when component mounts
  useEffect(() => {
    setIsPolling(true);
    return () => setIsPolling(false);
  }, []);

  // Check for pending videos on mount and periodically
  useEffect(() => {
    checkForPendingVideos();
    const interval = setInterval(checkForPendingVideos, 10000); // Every 10 seconds
    return () => clearInterval(interval);
  }, [checkForPendingVideos]);

  useEffect(() => {
    fetchGroupData();
    fetchLocations();
  }, [fetchGroupData, fetchLocations]);

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

  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading group videos...</div>
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
          <div style={{ marginBottom: '20px', color: '#666', fontSize: '14px' }}>
            URL attempted: /api/locations/{locationId}/groups/{groupId}/videos/
          </div>
          <button
            onClick={() => navigate(`/locations/${locationId}/groups`)}
            style={{
              padding: '10px 20px',
              border: '1px solid #3b82f6',
              borderRadius: '4px',
              backgroundColor: '#3b82f6',
              color: 'white',
              cursor: 'pointer',
              marginRight: '10px'
            }}
          >
            Back to Groups
          </button>
          <button
            onClick={fetchGroupData}
            style={{
              padding: '10px 20px',
              border: '1px solid #10b981',
              borderRadius: '4px',
              backgroundColor: '#10b981',
              color: 'white',
              cursor: 'pointer'
            }}
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!groupData) {
    return (
      <div className="main-content">
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <div style={{ color: '#ef4444', fontSize: '18px' }}>No group data available</div>
          <button
            onClick={fetchGroupData}
            style={{
              padding: '10px 20px',
              border: '1px solid #3b82f6',
              borderRadius: '4px',
              backgroundColor: '#3b82f6',
              color: 'white',
              cursor: 'pointer',
              marginTop: '16px'
            }}
          >
            Retry Loading
          </button>
        </div>
      </div>
    );
  }

  const { group = {}, videos = [] } = groupData;

  return (
    <div className="main-content">
      {/* Edit Video Modal */}
      <EditVideoModal
        isOpen={!!editingVideo}
        onClose={() => setEditingVideo(null)}
        video={editingVideo}
        onVideoUpdated={handleVideoUpdated}
        locations={locations}
      />

      {/* ✅ ADD: Pending videos notification */}
      {pendingVideos.length > 0 && (
        <div style={{
          padding: '12px 16px',
          backgroundColor: '#fef3c7',
          border: '1px solid #fbbf24',
          borderRadius: '8px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <span style={{ fontSize: '16px' }}>⏳</span>
          <span style={{ color: '#92400e', fontSize: '14px' }}>
            {pendingVideos.length} video{pendingVideos.length > 1 ? 's' : ''} processing...
            Page will auto-refresh when complete.
          </span>
        </div>
      )}

      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <button
            onClick={() => navigate('/locations')}
            style={{
              padding: '6px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: 'white',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Locations
          </button>
          <button
            onClick={() => navigate(`/locations/${locationId}/groups`)}
            style={{
              padding: '6px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: 'white',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            {formatLocationName(group.location)} Groups
          </button>
        </div>

        <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          {formatLocationName(group.location)} - {group.date || 'Unknown Date'}
        </h1>
        <p style={{ color: '#666', margin: 0 }}>
          {videos.length} videos sorted by time • {group.time_range || 'No time range'}
        </p>
      </div>

      {videos.length === 0 ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div style={{ fontSize: '64px', marginBottom: '16px', color: '#d1d5db' }}>🎬</div>
          <h3 style={{ marginBottom: '12px', color: '#374151' }}>No Videos in This Group</h3>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>
            No videos found for this date group.
          </p>
          <button
            onClick={() => navigate('/locations')}
            style={{
              padding: '10px 20px',
              border: '1px solid #3b82f6',
              borderRadius: '4px',
              backgroundColor: '#3b82f6',
              color: 'white',
              cursor: 'pointer'
            }}
          >
            Back to Locations
          </button>
        </div>
      ) : (
        <div className="dashboard-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ margin: 0 }}>Videos (Sorted by Time)</h2>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{
                backgroundColor: '#10b981',
                color: 'white',
                padding: '4px 8px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                {videos.length} videos
              </span>
              <span style={{
                backgroundColor: '#3b82f6',
                color: 'white',
                padding: '4px 8px',
                borderRadius: '12px',
                fontSize: '12px',
                fontWeight: '600'
              }}>
                {videos.reduce((total, video) => total + (video.vehicle_count || 0), 0)} total vehicles
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gap: '16px' }}>
            {videos.map((video, index) => (
              <div
                key={video.id}
                style={{
                  padding: '20px',
                  backgroundColor: '#f8fafc',
                  borderRadius: '8px',
                  border: '1px solid #e5e7eb',
                  transition: 'all 0.2s ease',
                  cursor: 'pointer'
                }}
                onClick={() => viewVideoAnalysis(video.id)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#f1f5f9';
                  e.currentTarget.style.borderColor = '#cbd5e1';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#f8fafc';
                  e.currentTarget.style.borderColor = '#e5e7eb';
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                      <span style={{
                        backgroundColor: '#3b82f6',
                        color: 'white',
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '14px',
                        fontWeight: '600',
                        flexShrink: 0
                      }}>
                        {index + 1}
                      </span>
                      <h3 style={{ margin: 0, color: '#1f2937', fontSize: '18px' }}>
                        {video.title || video.filename || 'Untitled Video'}
                      </h3>
                    </div>

                    <div style={{ marginLeft: '44px' }}>
                      {/* ✅ UPDATE: Use the helper function to format time */}
                      <p style={{ color: '#666', margin: '0 0 8px 0', fontSize: '14px' }}>
                        🕒 {formatVideoTime(video.start_time)} - {formatVideoTime(video.end_time)}
                        {formatDuration(video.duration)}
                      </p>

                      {video.vehicle_count > 0 && (
                        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
                          <span style={{
                            backgroundColor: '#10b981',
                            color: 'white',
                            padding: '4px 8px',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: '600'
                          }}>
                            {video.vehicle_count} vehicles
                          </span>
                          <span style={{
                            color: '#6b7280',
                            fontSize: '12px'
                          }}>
                            Processed
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexDirection: 'column', alignItems: 'flex-end' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        viewVideoAnalysis(video.id);
                      }}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid #3b82f6',
                        borderRadius: '6px',
                        backgroundColor: '#3b82f6',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '500',
                        minWidth: '120px'
                      }}
                      onMouseEnter={(e) => {
                        e.stopPropagation();
                        e.currentTarget.style.backgroundColor = '#2563eb';
                      }}
                      onMouseLeave={(e) => {
                        e.stopPropagation();
                        e.currentTarget.style.backgroundColor = '#3b82f6';
                      }}
                    >
                      View Analysis →
                    </button>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditVideo(video);
                      }}
                      style={{
                        padding: '6px 12px',
                        border: '1px solid #f59e0b',
                        borderRadius: '4px',
                        backgroundColor: 'white',
                        color: '#f59e0b',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: '500'
                      }}
                      onMouseEnter={(e) => {
                        e.stopPropagation();
                        e.currentTarget.style.backgroundColor = '#fef3c7';
                      }}
                      onMouseLeave={(e) => {
                        e.stopPropagation();
                        e.currentTarget.style.backgroundColor = 'white';
                      }}
                    >
                      Edit
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default GroupVideos;