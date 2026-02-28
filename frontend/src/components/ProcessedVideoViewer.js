import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.NODE_ENV === 'development' 
  ? 'http://127.0.0.1:8000' 
  : '';

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
          // Fetch session group data with videos — same call as before
          const groupResponse = await axios.get(`${API_BASE_URL}/api/location-groups/${videoId}/`);
          const groupData = groupResponse.data;
          
          setItemInfo(groupData); 
          
          const videosWithAnalysis = groupData.videos || [];
          setSessionVideos(videosWithAnalysis);
          
          if (videosWithAnalysis.length > 0) {
            const firstVideo = videosWithAnalysis[0];
            setSelectedVideo(firstVideo);
            setAnalysisData(firstVideo.analysis);
            setVideoUrl(`${API_BASE_URL}/api/video/${firstVideo.id}/view/`);
          }
          
        } else {
          // Single video mode — same call as before
          const analysisResponse = await axios.get(`${API_BASE_URL}/api/analysis/${videoId}/`);
          setAnalysisData(analysisResponse.data);
          setItemInfo(analysisResponse.data);
          setVideoUrl(`${API_BASE_URL}/api/video/${videoId}/view/`);
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
    setVideoUrl(`${API_BASE_URL}/api/video/${video.id}/view/`);
    setVideoLoadError(null);
  };

  const handleDownloadVideo = () => {
    if (type === 'session' && selectedVideo) {
      window.open(`${API_BASE_URL}/api/video/${selectedVideo.id}/download/`, '_blank');
    } else {
      window.open(`${API_BASE_URL}/api/video/${videoId}/download/`, '_blank');
    }
  };

  // Normalise the active analysis regardless of which API shape it came from.
  // Session videos:    video.analysis = { total_vehicles, congestion_level, car_count, ... }
  //                    (from LocationDateGroupDetailAPI)
  // Single video:      AnalysisResultsAPI returns { status, analysis: { total_vehicles,
  //                    vehicle_breakdown, processing_time, congestion_level, traffic_pattern,
  //                    analyzed_at, location }, video_info: { filename, ... } }
  const getActiveAnalysis = () => {
    if (type === 'session') {
      return selectedVideo?.analysis || null;
    }
    // For single video unwrap the nested .analysis if present
    return analysisData?.analysis || analysisData || null;
  };

  const renderQuickStats = () => {
    const data = getActiveAnalysis();
    if (!data) return null;

    // processing_time is the field name in AnalysisSummarySerializer;
    // processing_time_seconds is used in the session analysis object
    const procTime = data.processing_time_seconds ?? data.processing_time ?? 0;

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
              {Number(procTime).toFixed(1)}<span className="quick-stat-unit">s</span>
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
              {Number(data.average_traffic || 0).toFixed(1)}
            </div>
            <div className="quick-stat-label">Avg Traffic</div>
          </div>
        </div>
      </div>
    );
  };

  const renderVehicleBreakdown = () => {
    const data = getActiveAnalysis();
    if (!data) return null;

    // vehicle_breakdown from get_vehicle_breakdown() uses keys:
    //   car, truck, motorcycle, jeep, tricycle, other, total, directional_total
    // AnalysisSummarySerializer also passes vehicle_breakdown through unchanged.
    // Flat fallbacks (car_count etc.) cover the session analysis shape from
    // LocationDateGroupDetailAPI which only sets the flat count fields.
    const breakdown = data.vehicle_breakdown || {};
    const modelInfo = data.model_info || {};
    
    const vehicles = [
      { key: 'car',        label: 'Cars',        icon: '🚗',
        count: breakdown.car        ?? data.car_count        ?? 0, color: '#3b82f6' },
      { key: 'truck',      label: 'Trucks',       icon: '🚚',
        count: breakdown.truck      ?? data.truck_count      ?? 0, color: '#f59e0b' },
      { key: 'motorcycle', label: 'Motorcycles',  icon: '🏍️',
        count: breakdown.motorcycle ?? data.motorcycle_count ?? 0, color: '#ef4444' },
      // jeep is stored in bus_count in the DB; tricycle in bicycle_count
      { key: 'jeep',       label: 'Jeep',         icon: '🚌',
        count: breakdown.jeep    ?? breakdown.bus     ?? data.bus_count     ?? 0, color: '#8b5cf6' },
      { key: 'tricycle',   label: 'Tricycles',    icon: '🚲',
        count: breakdown.tricycle ?? breakdown.bicycle ?? data.bicycle_count ?? 0, color: '#10b981' },
      { key: 'other',      label: 'Others',       icon: '🚛',
        count: breakdown.other   ?? data.other_count  ?? 0, color: '#6b7280' },
    ].filter(v => v.count > 0);

    const total = data.total_vehicles || vehicles.reduce((sum, v) => sum + v.count, 0);
    const procTime = data.processing_time_seconds ?? data.processing_time ?? 0;

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
            <span className="summary-value">{Number(procTime).toFixed(1)}s</span>
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
                  {video.title || video.filename}
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
              Now Playing: <strong>{selectedVideo.title || selectedVideo.filename}</strong> 
              <span className="video-time">({selectedVideo.start_time} - {selectedVideo.end_time})</span>
            </p>
          )}
        </div>
        <div className="video-header-right">
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

  // Header title resolution:
  // Session: LocationDateGroupDetailAPI returns { location: {id, name}, date, time_range, ... }
  //          The original code read itemInfo?.group?.location?.display_name which was always
  //          undefined because there is no nested "group" key — it's top-level.
  // Single:  AnalysisResultsAPI returns { status, analysis:{...}, video_info:{filename,...} }
  const sessionLocationName =
    itemInfo?.location?.name ||           // actual API shape
    itemInfo?.group?.location?.display_name || // guard for any wrapper
    'Loading...';

  const singleVideoTitle =
    itemInfo?.video_info?.title ||
    itemInfo?.analysis?.video_info?.title ||
    'Loading...';

  return (
    <div className="main-content">
      {/* Header */}
      <div className="viewer-header">
        <div className="header-content">
          <h1>
            {type === 'session' 
              ? `Session: ${sessionLocationName}`
              : `Video: ${singleVideoTitle}`
            }
          </h1>
          {type === 'session' && itemInfo && (
            <div className="header-subtitle">
              <span>{new Date(itemInfo.date).toLocaleDateString()}</span>
              <span className="header-divider">•</span>
              <span>{sessionVideos.length} videos</span>
              <span className="header-divider">•</span>
              <span>{itemInfo.time_range || itemInfo.group?.time_range}</span>
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