import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const ProcessedVideoViewer = ({ videoId, type, onClose }) => {
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [itemInfo, setItemInfo] = useState(null);
  const [videoLoadError, setVideoLoadError] = useState(null);
  const [sessionVideos, setSessionVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const videoRef = useRef(null);

  useEffect(() => {
    const fetchItemData = async () => {
      try {
        setLoading(true);
        setError(null);

        if (type === 'session') {
          // Fetch session group data with videos
          const groupResponse = await axios.get(`http://127.0.0.1:8000/api/location-groups/${videoId}/`);
          const groupData = groupResponse.data;
          
          setItemInfo(groupData);
          
          // Get videos with their full analysis data
          const videosWithAnalysis = groupData.videos || [];
          setSessionVideos(videosWithAnalysis);
          
          // Select first video by default
          if (videosWithAnalysis.length > 0) {
            const firstVideo = videosWithAnalysis[0];
            setSelectedVideo(firstVideo);
            setAnalysisData(firstVideo.analysis);
            setVideoUrl(`http://127.0.0.1:8000/api/video/${firstVideo.id}/view/`);
          }
          
        } else {
          // Single video mode
          const analysisResponse = await axios.get(`http://127.0.0.1:8000/api/analysis/${videoId}/`);
          setAnalysisData(analysisResponse.data);
          setItemInfo(analysisResponse.data);
          setVideoUrl(`http://127.0.0.1:8000/api/video/${videoId}/view/`);
        }
        
      } catch (err) {
        console.error('Error loading data:', err);
        setError(err.response?.data?.error || err.message);
      } finally {
        setLoading(false);
      }
    };

    if (videoId && type) {
      fetchItemData();
    }
  }, [videoId, type]);

  const handleVideoSelect = (video) => {
    setSelectedVideo(video);
    setAnalysisData(video.analysis);
    setVideoUrl(`http://127.0.0.1:8000/api/video/${video.id}/view/`);
    setVideoLoadError(null);
  };

  // Add download function
  const handleDownloadVideo = () => {
    if (type === 'session' && selectedVideo) {
      // Download selected video from session
      const downloadUrl = `http://127.0.0.1:8000/api/video/${selectedVideo.id}/download/`;
      window.open(downloadUrl, '_blank');
    } else {
      // Download single video
      const downloadUrl = `http://127.0.0.1:8000/api/video/${videoId}/download/`;
      window.open(downloadUrl, '_blank');
    }
  };

  const renderQuickStats = () => {
    const data = type === 'session' && selectedVideo?.analysis 
      ? selectedVideo.analysis 
      : analysisData;
    
    if (!data) return null;

    return (
      <div className="quick-stats-container">
        <div className="quick-stat-card">
          <div className="quick-stat-icon">🚗</div>
          <div className="quick-stat-content">
            <div className="quick-stat-value">
              {data.total_vehicles || 0}
            </div>
            <div className="quick-stat-label">Total Vehicles</div>
          </div>
        </div>
        
        <div className="quick-stat-card">
          <div className="quick-stat-icon">⏱️</div>
          <div className="quick-stat-content">
            <div className="quick-stat-value">
              {(data.processing_time_seconds || 0).toFixed(1)}<span className="quick-stat-unit">s</span>
            </div>
            <div className="quick-stat-label">Processing Time</div>
          </div>
        </div>
        
        <div className="quick-stat-card">
          <div className="quick-stat-icon">🚦</div>
          <div className="quick-stat-content">
            <div className="quick-stat-value">
              {data.congestion_level || 'Unknown'}
            </div>
            <div className="quick-stat-label">Congestion</div>
          </div>
        </div>
        
        <div className="quick-stat-card">
          <div className="quick-stat-icon">📊</div>
          <div className="quick-stat-content">
            <div className="quick-stat-value">
              {data.traffic_pattern || 'Stable'}
            </div>
            <div className="quick-stat-label">Pattern</div>
          </div>
        </div>
        
        <div className="quick-stat-card">
          <div className="quick-stat-icon">📈</div>
          <div className="quick-stat-content">
            <div className="quick-stat-value">
              {data.peak_traffic || 0}
            </div>
            <div className="quick-stat-label">Peak Traffic</div>
          </div>
        </div>
        
        <div className="quick-stat-card">
          <div className="quick-stat-icon">📊</div>
          <div className="quick-stat-content">
            <div className="quick-stat-value">
              {(data.average_traffic || 0).toFixed(1)}
            </div>
            <div className="quick-stat-label">Avg Traffic</div>
          </div>
        </div>
      </div>
    );
  };

  const renderVehicleBreakdown = () => {
    const data = type === 'session' && selectedVideo?.analysis 
      ? selectedVideo.analysis 
      : analysisData;
    
    if (!data) return null;

    const breakdown = data.vehicle_breakdown || {};
    const modelInfo = data.model_info || {};
    
    const vehicles = [
      { key: 'car', label: 'Cars', icon: '🚗', count: breakdown.car || data.car_count || 0, color: '#3b82f6' },
      { key: 'truck', label: 'Trucks', icon: '🚚', count: breakdown.truck || data.truck_count || 0, color: '#f59e0b' },
      { key: 'motorcycle', label: 'Motorcycles', icon: '🏍️', count: breakdown.motorcycle || data.motorcycle_count || 0, color: '#ef4444' },
      { key: 'bus', label: 'Buses', icon: '🚌', count: breakdown.bus || data.bus_count || 0, color: '#8b5cf6' },
      { key: 'bicycle', label: 'Bicycles', icon: '🚲', count: breakdown.bicycle || data.bicycle_count || 0, color: '#10b981' },
      { key: 'other', label: 'Others', icon: '🚛', count: breakdown.other || data.other_count || 0, color: '#6b7280' }
    ].filter(v => v.count > 0);

    const total = data.total_vehicles || vehicles.reduce((sum, v) => sum + v.count, 0);

    return (
      <div className="analysis-section">
        <h3 className="section-title">
          <span>🚗</span> Vehicle Breakdown
        </h3>
        
        {modelInfo.model_name && (
          <div className="model-note">
            <strong>Model:</strong> {modelInfo.model_name}
            {modelInfo.detector_type && <span> ({modelInfo.detector_type})</span>}
          </div>
        )}
        
        <div className="vehicle-grid">
          {vehicles.map(vehicle => (
            <div 
              key={vehicle.key} 
              className="vehicle-type-card"
              style={{ borderLeftColor: vehicle.color }}
            >
              <div className="vehicle-type-header">
                <span className="vehicle-icon">{vehicle.icon}</span>
                <span className="vehicle-name">{vehicle.label}</span>
              </div>
              <div className="vehicle-count">{vehicle.count}</div>
              <div className="vehicle-percentage">
                {total > 0 ? ((vehicle.count / total) * 100).toFixed(1) : 0}%
              </div>
            </div>
          ))}
        </div>

        <div className="vehicle-summary">
          <div className="summary-item">
            <span className="summary-label">Total Vehicles</span>
            <span className="summary-value">{total}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Processing Time</span>
            <span className="summary-value">{(data.processing_time_seconds || 0).toFixed(1)}s</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">FPS</span>
            <span className="summary-value">{data.fps?.toFixed(1) || 'N/A'}</span>
          </div>
        </div>
      </div>
    );
  };

  const renderSessionVideos = () => {
    if (type !== 'session' || sessionVideos.length === 0) return null;
    
    return (
      <div className="analysis-section">
        <h3 className="section-title">
          🎬 Session Videos ({sessionVideos.length})
        </h3>
        
        <div className="session-videos-grid">
          {sessionVideos.map((video) => (
            <div
              key={video.id}
              onClick={() => handleVideoSelect(video)}
              className={`session-video-card ${selectedVideo?.id === video.id ? 'selected' : ''}`}
            >
              <div className="session-video-header">
                <div className="session-video-title">
                  {video.title}
                </div>
                {selectedVideo?.id === video.id && (
                  <div className="session-video-selected">Now Playing</div>
                )}
              </div>
              <div className="session-video-time">
                {video.start_time} - {video.end_time}
              </div>
              <div className="session-video-stats">
                <div className="session-video-stat">
                  <div className="session-stat-label">Vehicles</div>
                  <div className="session-stat-value">
                    {video.analysis?.total_vehicles || 0}
                  </div>
                </div>
                <div className="session-video-stat">
                  <div className="session-stat-label">Congestion</div>
                  <div className="session-stat-value congestion">
                    {video.analysis?.congestion_level || 'N/A'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderVideoPlayer = () => (
    <div className="analysis-section">
      <div className="video-player-header">
        <div className="video-header-left">
          <h3>Processed Video with Detection Overlay</h3>
          {type === 'session' && selectedVideo && (
            <p className="video-playing-info">
              Now Playing: <strong>{selectedVideo.title}</strong> 
              <span className="video-time">({selectedVideo.start_time} - {selectedVideo.end_time})</span>
            </p>
          )}
        </div>
        <div className="video-header-right">
          {/* Download button added here */}
          <button 
            onClick={handleDownloadVideo} 
            className="download-video-btn"
            title="Download this video"
          >
            ⬇️ Download Video
          </button>
        </div>
      </div>
      
      {videoUrl ? (
        <div>
          <video
            ref={videoRef}
            controls
            className="processed-video"
            onError={() => setVideoLoadError(true)}
            src={videoUrl}
          >
            Your browser does not support the video tag.
          </video>
          
          {videoLoadError && (
            <div className="video-error">
              <h4>Video Playback Issue</h4>
              <div className="video-error-content">
                <div className="video-error-tips">
                  <strong>If the video doesn't play:</strong>
                  <ul>
                    <li>Try refreshing the page</li>
                    <li>Check your internet connection</li>
                    <li>Try opening in a different browser</li>
                  </ul>
                </div>
                <div className="video-error-actions">
                  <div className="error-action-buttons">
                    <button 
                      className="error-action-btn"
                      onClick={() => window.open(videoUrl, '_blank')}
                    >
                      Open in New Tab
                    </button>
                    <button 
                      className="error-action-btn primary"
                      onClick={() => window.location.reload()}
                    >
                      Refresh Page
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="video-not-available">
          <div className="video-not-available-icon">📹</div>
          <h4>Processed video not available</h4>
          <p>The video file may still be processing or there might be an issue with the server.</p>
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="main-content">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p className="loading-text">Loading {type} data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="main-content">
        <div className="error-container">
          <div className="error-icon">❌</div>
          <p className="error-message">{error}</p>
          <button onClick={onClose} className="back-btn">
            Back to List
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      {/* Header */}
      <div className="viewer-header">
        <div className="header-content">
          <h1>
            {type === 'session' 
              ? `Session: ${itemInfo?.group?.location?.display_name || 'Loading...'}`
              : `Video: ${analysisData?.video_info?.title || 'Loading...'}`
            }
          </h1>
          {type === 'session' && itemInfo && (
            <div className="header-subtitle">
              <span>{new Date(itemInfo.group?.date).toLocaleDateString()}</span>
              <span className="header-divider">•</span>
              <span>{sessionVideos.length} videos</span>
              <span className="header-divider">•</span>
              <span>{itemInfo.group?.time_range}</span>
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="back-button"
        >
          ← Back
        </button>
      </div>

      {/* Session Videos */}
      {renderSessionVideos()}

      {/* Video Player */}
      {renderVideoPlayer()}

      {/* Quick Stats */}
      {renderQuickStats()}

      {/* Vehicle Breakdown */}
      {renderVehicleBreakdown()}
    </div>
  );
};

export default ProcessedVideoViewer;