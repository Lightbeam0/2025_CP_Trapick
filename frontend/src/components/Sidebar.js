// src/components/Sidebar.js - UPDATED with SmoothProgressBar
import React from "react";
import {
  FaChartLine, FaCarSide, FaTrafficLight,
  FaMagic, FaMapMarkerAlt, FaTimes,
} from "react-icons/fa";
import { useLocation } from 'react-router-dom';
import ProcessingResultModal from "./ProcessingResultModal";
import SmoothProgressBar from "./SmoothProgressBar";
import { useVideoProgress } from '../hooks/useVideoProgress';

function Sidebar({ isMobileOpen, onClose }) {
  const location = useLocation();
  const { progressStats, connectionStatus, isConnected } = useVideoProgress();

  const [processingResult, setProcessingResult] = React.useState(null);

  const isActiveLink = (href) => location.pathname === href;

  const handleNavigation = (href) => {
    if (window.innerWidth <= 768 && onClose) onClose();
    window.location.href = href;
  };

  // Show completion / failure modal
  React.useEffect(() => {
    if (!progressStats.details) return;
    Object.keys(progressStats.details).forEach(videoId => {
      const video = progressStats.details[videoId];
      if (video.status === 'completed' && video.video_info && !video.modalShown) {
        setProcessingResult({
          status: 'completed',
          message: 'Video processed successfully!',
          video_info: video.video_info,
        });
        progressStats.details[videoId].modalShown = true;
      }
      if (video.status === 'failed' && video.error_details && !video.modalShown) {
        setProcessingResult({
          status: 'failed',
          message: 'Processing failed',
          error_details: video.error_details,
        });
        progressStats.details[videoId].modalShown = true;
      }
    });
  }, [progressStats.details]);

  return (
    <>
      <div className={`sidebar ${isMobileOpen ? 'mobile-open' : ''}`}>
        {/* Mobile close button */}
        <button className="sidebar-close-button" onClick={onClose} aria-label="Close sidebar">
          <FaTimes size={20} />
        </button>

        <nav className="sidebar-nav">
          <ul className="sidebar-nav-list">
            {[
              { href: '/home',        icon: <FaChartLine />,    label: 'Overview' },
              { href: '/vehicles',    icon: <FaCarSide />,      label: 'Vehicles Passing' },
              { href: '/congested',   icon: <FaTrafficLight />, label: 'Congested Roads' },
              { href: '/locations',   icon: <FaMapMarkerAlt />, label: 'Locations' },
              { href: '/predictions', icon: <FaMagic />,        label: 'Traffic Predictions' },
            ].map(({ href, icon, label }) => (
              <li key={href}>
                <a
                  href={href}
                  className={`sidebar-nav-link ${
                    isActiveLink(href) || (href === '/home' && isActiveLink('/')) ? 'active' : ''
                  }`}
                  onClick={e => { e.preventDefault(); handleNavigation(href); }}
                >
                  {icon} <span>{label}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>

        {/* ── Progress section ─────────────────────────────────── */}
        {progressStats.total > 0 && (
          <div className="progress-section">

            {/* Active / processing videos */}
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

                    const displayName = video.filename
                      ? video.filename.length > 22
                        ? video.filename.substring(0, 22) + '…'
                        : video.filename
                      : videoId.substring(0, 8);

                    return (
                      <div key={videoId} className="progress-item">
                        <div className="progress-item-header">
                          <span className="progress-filename" title={video.filename}>
                            {displayName}
                          </span>
                        </div>

                        {/* ✨ Smooth animated bar */}
                        <SmoothProgressBar
                          progress={video.progress ?? 0}
                          status={video.status}
                          message={video.message}
                        />
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* Completed */}
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
                      <SmoothProgressBar
                        progress={100}
                        status="completed"
                        message={video.filename || videoId.substring(0, 8)}
                      />
                    </div>
                  );
                })}
              </div>
            )}

            {/* Failed */}
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
                      <SmoothProgressBar
                        progress={0}
                        status="failed"
                        message={video.filename || videoId.substring(0, 8)}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <ProcessingResultModal
          result={processingResult}
          onClose={() => setProcessingResult(null)}
        />
      </div>
    </>
  );
}

export default Sidebar;