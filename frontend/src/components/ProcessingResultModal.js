// src/components/ProcessingResultModal.js - UPDATED VERSION
import React, { useEffect, useState } from 'react';
import { FaCheckCircle, FaTimesCircle, FaVideo, FaMapMarkerAlt, FaCalendarAlt, FaCar } from 'react-icons/fa';

const ProcessingResultModal = ({ result, onClose, isOpen = true }) => {
  const [showAnimation, setShowAnimation] = useState(false);
  
  console.log("🔍 ProcessingResultModal - Current result:", result);
  console.log("🔍 ProcessingResultModal - Is open:", isOpen);
  
  useEffect(() => {
    if (result && isOpen) {
      // Trigger animation when modal appears
      setTimeout(() => setShowAnimation(true), 100);
      
      // Optional: Request notification permission
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
      }
    }
  }, [result, isOpen]);

  // Don't render if not open OR if no result
  if (!isOpen || !result) {
    console.log("❌ Modal: Not open or no result provided, not rendering");
    return null;
  }

  const { status, message, video_info, error_details } = result;

  // ✅ ADDED: Detailed debug logging
  if (result) {
    console.log('🔍 MODAL RENDERING with result:', {
      status: result.status,
      message: result.message,
      hasVideoInfo: !!result.video_info,
      videoInfo: result.video_info,
      hasErrorDetails: !!result.error_details
    });
  }

  console.log("🔍 Modal parsing data:", {
    status,
    message,
    video_info,
    error_details
  });

  // ✅ UPDATED: Check for both 'completed' and 'success' status
  const isSuccess = status === 'completed' || status === 'success';
  
  console.log("🔍 Modal isSuccess:", isSuccess);

  return (
    <div 
      className="modal-overlay" 
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        animation: 'fadeIn 0.3s ease-in'
      }}
    >
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        
        @keyframes slideUp {
          from { 
            opacity: 0;
            transform: translateY(30px) scale(0.9);
          }
          to { 
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        
        @keyframes successPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.1); }
        }
        
        .modal-content-animated {
          animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        
        .success-icon-animated {
          animation: successPulse 0.6s ease-in-out;
        }
        
        .modal-button-hover:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }
      `}</style>
      
      <div 
        className="modal-content modal-content-animated" 
        onClick={(e) => e.stopPropagation()} 
        style={{
          maxWidth: '550px',
          width: '90%',
          background: 'white',
          borderRadius: '16px',
          padding: '0',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)',
          overflow: 'hidden'
        }}
      >
        {/* Header with colored background */}
        <div style={{
          background: isSuccess 
            ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
            : 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
          padding: '32px 24px',
          textAlign: 'center',
          color: 'white',
          position: 'relative'
        }}>
          {/* Close button */}
          <button
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '16px',
              right: '16px',
              background: 'rgba(255, 255, 255, 0.2)',
              border: 'none',
              fontSize: '24px',
              cursor: 'pointer',
              color: 'white',
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.3)'}
            onMouseLeave={(e) => e.target.style.background = 'rgba(255, 255, 255, 0.2)'}
          >
            ×
          </button>

          {/* Success/Failure Icon */}
          <div className={showAnimation ? 'success-icon-animated' : ''} style={{
            fontSize: '64px',
            marginBottom: '16px'
          }}>
            {isSuccess ? (
              <FaCheckCircle style={{ color: 'white' }} />
            ) : (
              <FaTimesCircle style={{ color: 'white' }} />
            )}
          </div>

          <h2 style={{ 
            margin: '0 0 8px 0', 
            fontSize: '28px',
            fontWeight: '700'
          }}>
            {isSuccess ? 'Processing Complete!' : 'Processing Failed'}
          </h2>
          
          <p style={{ 
            margin: 0, 
            opacity: 0.95,
            fontSize: '16px'
          }}>
            {message}
          </p>
        </div>

        {/* Body with details */}
        <div style={{ padding: '24px' }}>
          {/* SUCCESS DETAILS */}
          {isSuccess && video_info && (
            <div style={{
              backgroundColor: '#f0fdf4',
              border: '2px solid #86efac',
              borderRadius: '12px',
              padding: '20px',
              marginBottom: '20px'
            }}>
              <h3 style={{ 
                margin: '0 0 16px 0', 
                color: '#166534',
                fontSize: '18px',
                fontWeight: '600'
              }}>
                Video Details
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {video_info.filename && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <FaVideo style={{ color: '#059669', fontSize: '18px' }} />
                    <div>
                      <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '500' }}>Filename</div>
                      <div style={{ fontSize: '14px', color: '#1f2937', fontWeight: '600' }}>{video_info.filename}</div>
                    </div>
                  </div>
                )}

                {video_info.location_name && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <FaMapMarkerAlt style={{ color: '#059669', fontSize: '18px' }} />
                    <div>
                      <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '500' }}>Location</div>
                      <div style={{ fontSize: '14px', color: '#1f2937', fontWeight: '600' }}>{video_info.location_name}</div>
                    </div>
                  </div>
                )}

                {video_info.group_date && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <FaCalendarAlt style={{ color: '#059669', fontSize: '18px' }} />
                    <div>
                      <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '500' }}>Date</div>
                      <div style={{ fontSize: '14px', color: '#1f2937', fontWeight: '600' }}>{video_info.group_date}</div>
                    </div>
                  </div>
                )}

                {video_info.total_vehicles !== undefined && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <FaCar style={{ color: '#059669', fontSize: '18px' }} />
                    <div>
                      <div style={{ fontSize: '12px', color: '#6b7280', fontWeight: '500' }}>Vehicles Detected</div>
                      <div style={{ fontSize: '20px', color: '#059669', fontWeight: '700' }}>{video_info.total_vehicles}</div>
                    </div>
                  </div>
                )}
              </div>

              {video_info.group_id && (
                <div style={{ 
                  marginTop: '16px', 
                  paddingTop: '16px', 
                  borderTop: '1px solid #86efac' 
                }}>
                  <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Group ID</div>
                  <code style={{ 
                    fontSize: '13px', 
                    color: '#059669',
                    backgroundColor: '#dcfce7',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontFamily: 'monospace'
                  }}>
                    {video_info.group_id}
                  </code>
                </div>
              )}
            </div>
          )}

          {/* ERROR DETAILS */}
          {!isSuccess && error_details && (
            <div style={{
              backgroundColor: '#fef2f2',
              border: '2px solid #fca5a5',
              borderRadius: '12px',
              padding: '20px',
              marginBottom: '20px'
            }}>
              <h3 style={{ 
                margin: '0 0 12px 0', 
                color: '#991b1b',
                fontSize: '16px',
                fontWeight: '600'
              }}>
                Error Details
              </h3>
              <p style={{ 
                margin: 0, 
                color: '#7f1d1d',
                fontSize: '14px',
                lineHeight: '1.6'
              }}>
                {error_details.error_message || error_details || 'An unexpected error occurred during processing.'}
              </p>
            </div>
          )}

          {/* ACTION BUTTONS */}
          <div style={{ display: 'flex', gap: '12px', flexDirection: 'column' }}>
            {isSuccess && video_info?.group_id && (
              <a
                href={`/locations/${video_info.location_id || '1'}/groups/${video_info.group_id}`}
                className="modal-button-hover"
                style={{
                  display: 'block',
                  padding: '14px 20px',
                  backgroundColor: '#3b82f6',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: '10px',
                  textAlign: 'center',
                  fontWeight: '600',
                  fontSize: '15px',
                  transition: 'all 0.2s',
                  boxShadow: '0 2px 8px rgba(59, 130, 246, 0.3)'
                }}
              >
                📊 View Analysis Results
              </a>
            )}

            {isSuccess && (
              <a
                href="/locations"
                className="modal-button-hover"
                style={{
                  display: 'block',
                  padding: '14px 20px',
                  backgroundColor: '#f3f4f6',
                  color: '#374151',
                  textDecoration: 'none',
                  borderRadius: '10px',
                  textAlign: 'center',
                  fontWeight: '600',
                  fontSize: '15px',
                  transition: 'all 0.2s'
                }}
              >
                📹 Browse All Videos
              </a>
            )}

            <button
              onClick={onClose}
              className="modal-button-hover"
              style={{
                width: '100%',
                padding: '14px 20px',
                backgroundColor: isSuccess ? '#10b981' : '#6b7280',
                color: 'white',
                border: 'none',
                borderRadius: '10px',
                cursor: 'pointer',
                fontWeight: '600',
                fontSize: '15px',
                transition: 'all 0.2s'
              }}
            >
              {isSuccess ? '✓ Got it!' : 'Close'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProcessingResultModal;