// src/components/Sidebar.js - UPDATED VERSION
import React from "react";
import { FaChartLine, FaCarSide, FaTrafficLight, FaCog, FaUpload, FaMagic, FaMapMarkerAlt } from "react-icons/fa";
import { useLocation } from 'react-router-dom';
import VideoUploadModal from "./VideoUploadModal";
import ProcessingResultModal from "./ProcessingResultModal";
import { useVideoProgress } from '../hooks/useVideoProgress';

function Sidebar() {
  const location = useLocation();
  const { progressStats, connectionStatus, isConnected } = useVideoProgress();
  
  const [isUploadModalOpen, setIsUploadModalOpen] = React.useState(false);
  const [processingResult, setProcessingResult] = React.useState(null);

  const isActiveLink = (href) => location.pathname === href;

  // CRITICAL: Listen for completion events and show modal
  React.useEffect(() => {
    if (!progressStats.details) return;

    Object.keys(progressStats.details).forEach(videoId => {
      const video = progressStats.details[videoId];
      
      console.log(`🔍 Checking video ${videoId}:`, {
        status: video.status,
        hasVideoInfo: !!video.video_info,
        modalShown: video.modalShown
      });
      
      // Only trigger modal once when status becomes 'completed'
      if (video.status === 'completed' && video.video_info && !video.modalShown) {
        console.log('🎉 TRIGGERING SUCCESS MODAL for:', videoId);
        
        setProcessingResult({
          status: 'completed',  // ✅ CHANGED: Use 'status' instead of 'type'
          message: 'Video processed successfully!',
          video_info: video.video_info
        });
        
        // Mark as shown to prevent duplicate modals
        progressStats.details[videoId].modalShown = true;
      }
      
      // Handle failures
      if (video.status === 'failed' && video.error_details && !video.modalShown) {
        console.log('❌ TRIGGERING ERROR MODAL for:', videoId);
        
        setProcessingResult({
          status: 'failed',  // ✅ CHANGED: Use 'status' instead of 'type'
          message: 'Processing failed',
          error_details: video.error_details  // ✅ CHANGED: Use 'error_details' not 'error'
        });
        
        progressStats.details[videoId].modalShown = true;
      }
    });
  }, [progressStats.details]);

  const handleUploadSuccess = (result) => {
    console.log("Upload successful:", result);
    setIsUploadModalOpen(false);
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>Traffic Monitor</h1>
        <p>Zamboanga City</p>
        <small style={{
          color: isConnected ? '#10b981' : '#ef4444',
          fontSize: '11px',
          display: 'block',
          marginTop: '4px'
        }}>
          {isConnected ? 'Live' : 'Offline'}
        </small>
      </div>

      <nav className="sidebar-nav">
        <ul className="sidebar-nav-list">
          <li><a href="/" className={`sidebar-nav-link ${isActiveLink('/') ? 'active' : ''}`}><FaChartLine /> <span>Overview</span></a></li>
          <li><a href="/vehicles" className={`sidebar-nav-link ${isActiveLink('/vehicles') ? 'active' : ''}`}><FaCarSide /> <span>Vehicles Passing</span></a></li>
          <li><a href="/congested" className={`sidebar-nav-link ${isActiveLink('/congested') ? 'active' : ''}`}><FaTrafficLight /> <span>Congested Roads</span></a></li>
          <li><a href="/locations" className={`sidebar-nav-link ${isActiveLink('/locations') ? 'active' : ''}`}><FaMapMarkerAlt /> <span>Locations</span></a></li>
          <li><a href="/predictions" className={`sidebar-nav-link ${isActiveLink('/predictions') ? 'active' : ''}`}><FaMagic /> <span>Traffic Predictions</span></a></li>
          <li><a href="/settings" className={`sidebar-nav-link ${isActiveLink('/settings') ? 'active' : ''}`}><FaCog /> <span>Settings</span></a></li>
        </ul>
      </nav>

      {/* PROGRESS SECTION */}
      {progressStats.total > 0 && (
        <div className="progress-section">
          {/* PROCESSING */}
          {progressStats.active > 0 && (
            <>
              <div className="progress-header">
                <span className="progress-spinner">⏳</span>
                <span className="progress-title">Processing ({progressStats.active})</span>
              </div>
              <div className="progress-list">
                {progressStats.videoIds.map(videoId => {
                  const video = progressStats.details[videoId];
                  if (video.status !== 'processing') return null;

                  return (
                    <div key={videoId} className="progress-item">
                      <div className="progress-item-header">
                        <span className="progress-filename" title={video.filename}>
                          {video.filename?.length > 20 
                            ? video.filename.substring(0, 20) + '...' 
                            : video.filename || videoId.substring(0, 8)}
                        </span>
                        <span className="progress-percentage">{video.progress}%</span>
                      </div>
                      <div className="progress-bar-container">
                        <div 
                          className="progress-bar"
                          style={{ 
                            width: `${video.progress}%`,
                            backgroundColor: video.progress >= 100 ? '#10b981' : '#3b82f6'
                          }}
                        ></div>
                      </div>
                      <div className="progress-message">{video.message}</div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* COMPLETED */}
          {progressStats.completed > 0 && (
            <div className="completed-section">
              <div className="completed-header">
                <span className="completed-icon">✅</span>
                <span>Completed ({progressStats.completed})</span>
              </div>
              {progressStats.videoIds.map(videoId => {
                const video = progressStats.details[videoId];
                if (video.status !== 'completed') return null;
                return (
                  <div key={videoId} className="completed-item">
                    {video.filename || videoId.substring(0, 8)}
                  </div>
                );
              })}
            </div>
          )}

          {/* FAILED */}
          {progressStats.failed > 0 && (
            <div className="failed-section">
              <div className="failed-header">
                <span className="failed-icon">❌</span>
                <span>Failed ({progressStats.failed})</span>
              </div>
              {progressStats.videoIds.map(videoId => {
                const video = progressStats.details[videoId];
                if (video.status !== 'failed') return null;
                return (
                  <div key={videoId} className="failed-item">
                    {video.filename || videoId.substring(0, 8)}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <button onClick={() => setIsUploadModalOpen(true)} className="upload-button">
        <FaUpload className="upload-icon" />
        <span>Upload Video</span>
      </button>

      {/* MODALS */}
      <ProcessingResultModal
        result={processingResult}
        onClose={() => setProcessingResult(null)}
      />
      <VideoUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadSuccess}
      />
    </div>
  );
}

export default Sidebar;