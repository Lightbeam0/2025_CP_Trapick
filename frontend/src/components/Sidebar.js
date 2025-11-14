// src/components/Sidebar.js
import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { FaChartLine, FaCarSide, FaTrafficLight, FaCog, FaUpload, FaMagic, FaMapMarkerAlt, FaSpinner, FaCheck, FaTimes } from "react-icons/fa";
import VideoUploadModal from "./VideoUploadModal";

function Sidebar() {
  const location = useLocation();
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [processingVideos, setProcessingVideos] = useState({});

  // Poll for progress updates
  useEffect(() => {
    const pollProgress = async () => {
      try {
        // Get all videos
        const response = await fetch('/api/videos/');
        const videos = await response.json();
        
        const updatedProcessing = {};
        
        for (const video of videos) {
          const videoId = video.id;
          
          // Only check progress for videos that are not completed/failed in our local state
          // OR if they're still processing on the server
          if (video.processing_status === 'processing' || 
              video.processing_status === 'uploaded' ||
              (processingVideos[videoId] && processingVideos[videoId].status === 'processing')) {
            
            try {
              // Get current progress from the progress endpoint
              const progressResponse = await fetch(`/api/videos/${videoId}/progress/`);
              if (progressResponse.ok) {
                const progressData = await progressResponse.json();
                
                updatedProcessing[videoId] = {
                  progress: progressData.progress || 0,
                  message: progressData.message || 'Processing...',
                  status: progressData.status || 'processing',
                  filename: video.filename || video.title || 'Unknown file',
                  id: videoId
                };
              } else {
                // If progress endpoint fails, use video status
                updatedProcessing[videoId] = {
                  progress: video.processing_status === 'completed' ? 100 : 0,
                  message: getStatusMessage(video.processing_status),
                  status: video.processing_status === 'completed' ? 'completed' : 
                         video.processing_status === 'failed' ? 'failed' : 'processing',
                  filename: video.filename || video.title || 'Unknown file',
                  id: videoId
                };
              }
            } catch (error) {
              console.error(`Error getting progress for ${videoId}:`, error);
              // Fallback to video status
              updatedProcessing[videoId] = {
                progress: video.processing_status === 'completed' ? 100 : 0,
                message: getStatusMessage(video.processing_status),
                status: video.processing_status === 'completed' ? 'completed' : 
                       video.processing_status === 'failed' ? 'failed' : 'processing',
                filename: video.filename || video.title || 'Unknown file',
                id: videoId
              };
            }
          }
        }
        
        setProcessingVideos(updatedProcessing);
      } catch (error) {
        console.error('Error polling progress:', error);
      }
    };

    // Helper function to get status messages
    const getStatusMessage = (status) => {
      switch (status) {
        case 'uploaded': return 'Waiting to start processing...';
        case 'processing': return 'Processing video...';
        case 'completed': return 'Processing completed!';
        case 'failed': return 'Processing failed!';
        default: return 'Unknown status';
      }
    };

    // Poll every 2 seconds for better responsiveness
    const interval = setInterval(pollProgress, 2000);
    
    // Initial poll
    pollProgress();

    return () => clearInterval(interval);
  }, [processingVideos]); // Add processingVideos to dependencies to detect changes

  const menuItems = [
    { path: "/", label: "Overview", icon: <FaChartLine /> },
    { path: "/vehicles", label: "Vehicles Passing", icon: <FaCarSide /> },
    { path: "/congested", label: "Congested Roads", icon: <FaTrafficLight /> },
    { path: "/locations", label: "Locations", icon: <FaMapMarkerAlt /> },
    { path: "/predictions", label: "Traffic Predictions", icon: <FaMagic /> },
    { path: "/settings", label: "Settings", icon: <FaCog /> },
  ];  

  const handleUploadSuccess = (result) => {
    console.log("Upload successful - Full result:", result);
    setIsUploadModalOpen(false);
    
    // Extract the upload ID and filename safely
    const uploadId = result.upload_id || result.id;
    const filename = result.video_info?.filename || 
                    result.filename || 
                    'Uploading...';
    
    if (uploadId) {
      alert(`Video uploaded successfully! Processing ID: ${uploadId}`);
      
      // Add the new video to processing list immediately with initial state
      setProcessingVideos(prev => ({
        ...prev,
        [uploadId]: {
          progress: 0,
          message: 'Upload complete, starting processing...',
          status: 'processing',
          filename: filename,
          id: uploadId
        }
      }));
    } else {
      alert('Video uploaded successfully!');
    }
  };

  // Get all processing videos (including completed/failed for display)
  const allProcessingVideos = Object.values(processingVideos);
  
  // Separate active processing from completed/failed
  const activeProcessing = allProcessingVideos.filter(
    video => video.status === 'processing'
  );
  
  const completedVideos = allProcessingVideos.filter(
    video => video.status === 'completed'
  );
  
  const failedVideos = allProcessingVideos.filter(
    video => video.status === 'failed'
  );

  // Auto-remove completed videos after 10 seconds
  useEffect(() => {
    if (completedVideos.length > 0) {
      const timer = setTimeout(() => {
        setProcessingVideos(prev => {
          const updated = { ...prev };
          completedVideos.forEach(video => {
            delete updated[video.id];
          });
          return updated;
        });
      }, 10000); // Remove after 10 seconds
      
      return () => clearTimeout(timer);
    }
  }, [completedVideos]);

  // Auto-remove failed videos after 15 seconds
  useEffect(() => {
    if (failedVideos.length > 0) {
      const timer = setTimeout(() => {
        setProcessingVideos(prev => {
          const updated = { ...prev };
          failedVideos.forEach(video => {
            delete updated[video.id];
          });
          return updated;
        });
      }, 15000); // Remove after 15 seconds
      
      return () => clearTimeout(timer);
    }
  }, [failedVideos]);

  return (
    <>
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>Traffic Monitor</h1>
          <p>Zamboanga City</p>
        </div>

        <nav className="sidebar-nav">
          <ul className="sidebar-nav-list">
            {menuItems.map((item) => (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`sidebar-nav-link ${location.pathname === item.path ? 'active' : ''}`}
                >
                  <span className="sidebar-nav-icon">{item.icon}</span>
                  <span>{item.label}</span>
                  {location.pathname === item.path && (
                    <span className="active-indicator"></span>
                  )}
                </Link>
              </li>
            ))}
          </ul>

          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="upload-button"
          >
            <FaUpload className="upload-icon" />
            <span>Upload Video</span>
          </button>
        </nav>

        {/* Progress Tracking Section in Sidebar */}
        {(activeProcessing.length > 0 || completedVideos.length > 0 || failedVideos.length > 0) && (
          <div className="progress-section">
            {/* Active Processing */}
            {activeProcessing.length > 0 && (
              <>
                <div className="progress-header">
                  <FaSpinner className="progress-spinner" />
                  <span className="progress-title">
                    Processing ({activeProcessing.length})
                  </span>
                </div>
                
                <div className="progress-list">
                  {activeProcessing.map((video) => (
                    <div key={video.id} className="progress-item">
                      <div className="progress-item-header">
                        <span className="progress-filename">
                          {video.filename}
                        </span>
                        <span className="progress-percentage">
                          {video.progress}%
                        </span>
                      </div>
                      <div className="progress-bar-container">
                        <div 
                          className="progress-bar"
                          style={{ width: `${video.progress}%` }}
                        ></div>
                      </div>
                      <div className="progress-message">
                        {video.message}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Completed Videos */}
            {completedVideos.length > 0 && (
              <div className="completed-section">
                <div className="completed-header">
                  <FaCheck className="completed-icon" />
                  <span className="completed-title">
                    Completed ({completedVideos.length})
                  </span>
                </div>
                {completedVideos.map((video) => (
                  <div key={video.id} className="completed-item">
                    ✓ {video.filename}
                  </div>
                ))}
              </div>
            )}

            {/* Failed Videos */}
            {failedVideos.length > 0 && (
              <div className="failed-section">
                <div className="failed-header">
                  <FaTimes className="failed-icon" />
                  <span className="failed-title">
                    Failed ({failedVideos.length})
                  </span>
                </div>
                {failedVideos.map((video) => (
                  <div key={video.id} className="failed-item">
                    ✗ {video.filename}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="sidebar-footer">
          <p></p>
          <p></p>
        </div>
      </div>

      <VideoUploadModal 
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadSuccess}
      />
    </>
  );
}

export default Sidebar;