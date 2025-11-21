// src/components/ProcessingResultModal.js - Enhanced with debugging
import React from 'react';

const ProcessingResultModal = ({ result, onClose }) => {
  console.log("🔍 ProcessingResultModal - Current result:", result);
  
  if (!result) {
    console.log("❌ Modal: No result provided, not rendering");
    return null;
  }

  const { status, message, video_info, error_details, video_id } = result;
  
  console.log("🔍 Modal parsing data:", {
    status,
    message, 
    video_info,
    error_details,
    video_id
  });

  const isSuccess = status === 'completed';
  const icon = isSuccess ? '✅' : '❌';
  const title = isSuccess ? 'Processing Successful!' : 'Processing Failed!';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ 
        maxWidth: '500px', 
        background: 'white', 
        borderRadius: '8px',
        padding: '20px',
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
      }}>
        <div className="modal-header" style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '16px',
          borderBottom: '1px solid #e2e8f0',
          paddingBottom: '12px'
        }}>
          <h2 style={{ margin: 0, color: isSuccess ? '#2d3748' : '#718096' }}>
            {icon} {title}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              cursor: 'pointer',
              color: '#666'
            }}
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          <div style={{ 
            backgroundColor: isSuccess ? '#f0fff4' : '#fed7d7',
            color: isSuccess ? '#2f855a' : '#c53030',
            padding: '16px',
            borderRadius: '6px',
            marginBottom: '16px'
          }}>
            <p style={{ margin: '0 0 8px 0', fontWeight: 'bold' }}>{message}</p>
            
            {isSuccess && video_info && (
              <div style={{ marginTop: '12px', fontSize: '14px' }}>
                <p><strong>Video ID:</strong> {video_id}</p>
                {video_info.filename && <p><strong>Filename:</strong> {video_info.filename}</p>}
                {video_info.location_name && <p><strong>Location:</strong> {video_info.location_name}</p>}
                {video_info.group_date && <p><strong>Date:</strong> {video_info.group_date}</p>}
                {video_info.total_vehicles !== undefined && (
                  <p><strong>Total Vehicles:</strong> {video_info.total_vehicles}</p>
                )}
              </div>
            )}
            
            {!isSuccess && error_details && (
              <div style={{ marginTop: '12px', fontSize: '14px' }}>
                <p><strong>Error Details:</strong> {error_details.error_message}</p>
              </div>
            )}
          </div>

          {isSuccess && video_info && (
            <div style={{ display: 'flex', gap: '12px', flexDirection: 'column' }}>
              {video_info.group_id && (
                <a
                  href={`/location-groups/${video_info.group_id}`}
                  style={{
                    display: 'block',
                    padding: '12px 16px',
                    backgroundColor: '#4299e1',
                    color: 'white',
                    textDecoration: 'none',
                    borderRadius: '6px',
                    textAlign: 'center',
                    fontWeight: 'bold'
                  }}
                >
                  View Analysis Results
                </a>
              )}
              <a
                href="/videos"
                style={{
                  display: 'block',
                  padding: '12px 16px',
                  backgroundColor: '#e2e8f0',
                  color: '#4a5568',
                  textDecoration: 'none',
                  borderRadius: '6px',
                  textAlign: 'center'
                }}
              >
                Browse All Videos
              </a>
            </div>
          )}
        </div>

        <div className="modal-footer" style={{ marginTop: '16px' }}>
          <button
            onClick={onClose}
            style={{
              width: '100%',
              padding: '12px 16px',
              backgroundColor: '#e2e8f0',
              color: '#4a5568',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProcessingResultModal;