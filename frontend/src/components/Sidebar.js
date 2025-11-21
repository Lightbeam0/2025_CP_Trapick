// src/components/Sidebar.js
import React, { useState, useEffect, useRef } from "react";
import { FaChartLine, FaCarSide, FaTrafficLight, FaCog, FaUpload, FaMagic, FaMapMarkerAlt, FaSpinner, FaCheck, FaTimes } from "react-icons/fa";
import { useLocation } from 'react-router-dom'; // Import useLocation
import VideoUploadModal from "./VideoUploadModal";
import ProcessingResultModal from "./ProcessingResultModal";

function Sidebar() {
  const location = useLocation(); // Get the current location

  const [processingVideos, setProcessingVideos] = useState({});
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('Connecting...');
  const [processingResult, setProcessingResult] = useState(null);
  const wsRef = useRef(null);

  // Function to determine if a link should be active
  const isActiveLink = (href) => {
    return location.pathname === href;
  };

  const connectToGeneralProgressWS = () => {
    if (wsRef.current) {
        wsRef.current.close();
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//127.0.0.1:8000/ws/progress/`;

    console.log("🔌 Attempting to connect to general progress WebSocket:", wsUrl);
    setConnectionStatus('Connecting...');

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("✅ General Progress WebSocket connected");
        setWsConnected(true);
        setConnectionStatus('Live');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("📨 Sidebar received WebSocket message:", data);

          if (data.type === 'progress_update') {
            console.log(`📊 Updating progress for ${data.video_id}: ${data.progress}% - ${data.message}`);
            setProcessingVideos(prev => ({
              ...prev,
              [data.video_id]: {
                ...prev[data.video_id],
                progress: data.progress,
                message: data.message,
                status: 'processing',
                id: data.video_id,
                filename: prev[data.video_id]?.filename || 'Unknown'
              }
            }));
          } 
          else if (data.type === 'processing_complete') {
            console.log(`✅ Processing complete for ${data.video_id}:`, data);
            
            setProcessingVideos(prev => ({
              ...prev,
              [data.video_id]: {
                ...prev[data.video_id],
                progress: 100,
                message: data.message,
                status: 'completed',
                id: data.video_id,
                filename: prev[data.video_id]?.filename || 'Unknown'
              }
            }));

            const modalData = {
              status: 'completed',
              message: data.message || 'Processing completed successfully!',
              video_id: data.video_id,
              video_info: data.video_info || {}
            };
            
            console.log("🎯 Setting modal data:", modalData);
            setProcessingResult(modalData);

          } 
          else if (data.type === 'processing_failed') {
            console.log(`❌ Processing failed for ${data.video_id}:`, data);
            
            setProcessingVideos(prev => ({
              ...prev,
              [data.video_id]: {
                ...prev[data.video_id],
                progress: 0,
                message: data.message,
                status: 'failed',
                id: data.video_id,
                filename: prev[data.video_id]?.filename || 'Unknown'
              }
            }));

            const modalData = {
              status: 'failed',
              message: data.message || 'Processing failed!',
              video_id: data.video_id,
              error_details: data.error_details || {}
            };
            
            console.log("🎯 Setting modal data:", modalData);
            setProcessingResult(modalData);
          } 
          else if (data.type === 'all_progress') {
            console.log("📊 Received initial progress data:", data.progress_data);
            setProcessingVideos(data.progress_data);
          } 
          else {
            console.warn("⚠️ Sidebar received unknown message type:", data.type, data);
          }
        } catch (error) {
          console.error("❌ Error parsing WebSocket message in Sidebar:", error, event.data);
        }
      };

      ws.onclose = (event) => {
        console.log(`❌ WebSocket closed: Code ${event.code}, Reason: ${event.reason}`);
        setWsConnected(false);
        setConnectionStatus(`Disconnected (${event.code})`);
        
        setTimeout(() => {
          console.log("🔄 Attempting to reconnect WebSocket...");
          connectToGeneralProgressWS();
        }, 3000);
      };

      ws.onerror = (error) => {
        console.error("❌ WebSocket error:", error);
        setWsConnected(false);
        setConnectionStatus('Connection Error');
      };
    } catch (error) {
      console.error("❌ Error creating WebSocket connection:", error);
      setWsConnected(false);
      setConnectionStatus('Connection Failed');
    }
  };

  useEffect(() => {
    connectToGeneralProgressWS();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    const pollProgress = async () => {
      if (wsConnected) {
        return;
      }
      console.log("🔄 Polling for progress (fallback)...");
      try {
        const response = await fetch('http://127.0.0.1:8000/api/progress/active/');
        if (response.ok) {
          const progressData = await response.json();
          setProcessingVideos(progressData);
        }
      } catch (error) {
        console.error('Error polling progress:', error);
      }
    };

    const interval = setInterval(pollProgress, wsConnected ? 30000 : 10000);
    pollProgress();

    return () => clearInterval(interval);
  }, [wsConnected]);

  const handleUploadSuccess = (result) => {
    console.log("Upload successful:", result);
    setIsUploadModalOpen(false);

    const uploadId = result.upload_id || result.id;
    const filename = result.video_info?.filename || result.filename || 'Uploading...';

    if (uploadId) {
      setProcessingVideos(prev => ({
        ...prev,
        [uploadId]: {
          progress: 0,
          message: 'Upload complete, starting processing...',
          status: 'uploaded',
          filename: filename,
          id: uploadId
        }
      }));
    }
  };

  const allProcessingVideos = Object.values(processingVideos);
  const activeProcessing = allProcessingVideos.filter(v =>
    v.status === 'uploaded' || v.status === 'processing'
  );
  const completedVideos = allProcessingVideos.filter(v => v.status === 'completed');
  const failedVideos = allProcessingVideos.filter(v => v.status === 'failed');

  useEffect(() => {
    const videosToRemove = [...completedVideos, ...failedVideos];
    if (videosToRemove.length > 0) {
      const timer = setTimeout(() => {
        setProcessingVideos(prev => {
          const updated = { ...prev };
          videosToRemove.forEach(video => {
            delete updated[video.id];
          });
          return updated;
        });
      }, 10000);
      return () => clearTimeout(timer);
    }
  }, [completedVideos, failedVideos]);

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>Traffic Monitor</h1>
        <p>Zamboanga City</p>
      </div>

      <nav className="sidebar-nav">
        <ul className="sidebar-nav-list">
          <li>
            {/* Use the isActiveLink function */}
            <a href="/" className={`sidebar-nav-link ${isActiveLink('/') ? 'active' : ''}`}>
              <span className="sidebar-nav-icon"><FaChartLine /></span>
              <span>Overview</span>
              {/* The active indicator is now correctly associated with the active link */}
              {isActiveLink('/') && <span className="active-indicator"></span>}
            </a>
          </li>
          <li>
            {/* Use the isActiveLink function */}
            <a href="/vehicles" className={`sidebar-nav-link ${isActiveLink('/vehicles') ? 'active' : ''}`}>
              <span className="sidebar-nav-icon"><FaCarSide /></span>
              <span>Vehicles Passing</span>
              {isActiveLink('/vehicles') && <span className="active-indicator"></span>}
            </a>
          </li>
          <li>
            {/* Use the isActiveLink function */}
            <a href="/congested" className={`sidebar-nav-link ${isActiveLink('/congested') ? 'active' : ''}`}>
              <span className="sidebar-nav-icon"><FaTrafficLight /></span>
              <span>Congested Roads</span>
              {isActiveLink('/congested') && <span className="active-indicator"></span>}
            </a>
          </li>
          <li>
            {/* Use the isActiveLink function */}
            <a href="/locations" className={`sidebar-nav-link ${isActiveLink('/locations') ? 'active' : ''}`}>
              <span className="sidebar-nav-icon"><FaMapMarkerAlt /></span>
              <span>Locations</span>
              {isActiveLink('/locations') && <span className="active-indicator"></span>}
            </a>
          </li>
          <li>
            {/* Use the isActiveLink function */}
            <a href="/predictions" className={`sidebar-nav-link ${isActiveLink('/predictions') ? 'active' : ''}`}>
              <span className="sidebar-nav-icon"><FaMagic /></span>
              <span>Traffic Predictions</span>
              {isActiveLink('/predictions') && <span className="active-indicator"></span>}
            </a>
          </li>
          <li>
            {/* Use the isActiveLink function */}
            <a href="/settings" className={`sidebar-nav-link ${isActiveLink('/settings') ? 'active' : ''}`}>
              <span className="sidebar-nav-icon"><FaCog /></span>
              <span>Settings</span>
              {isActiveLink('/settings') && <span className="active-indicator"></span>}
            </a>
          </li>
        </ul>
      </nav>

      {(activeProcessing.length > 0 || completedVideos.length > 0 || failedVideos.length > 0) && (
        <div className="progress-section">

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
                      <span className="progress-filename" title={video.filename}>
                        {video.filename.length > 20
                          ? video.filename.substring(0, 20) + '...'
                          : video.filename}
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

          {completedVideos.length > 0 && (
            <div className="completed-section">
              <div className="completed-header">
                <FaCheck className="completed-icon" />
                <span>Completed ({completedVideos.length})</span>
              </div>
              {completedVideos.map((video) => (
                <div key={video.id} className="completed-item">
                  ✓ {video.filename}
                </div>
              ))}
            </div>
          )}

          {failedVideos.length > 0 && (
            <div className="failed-section">
              <div className="failed-header">
                <FaTimes className="failed-icon" />
                <span>Failed ({failedVideos.length})</span>
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

      <button
        onClick={() => setIsUploadModalOpen(true)}
        className="upload-button"
      >
        <FaUpload className="upload-icon" />
        <span>Upload Video</span>
      </button>

      <ProcessingResultModal
        result={processingResult}
        onClose={() => setProcessingResult(null)}
      />

      <VideoUploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadSuccess}
      />

      <div className="sidebar-footer">
        <p></p>
        <p></p>
      </div>
    </div>
  );
}

export default Sidebar;