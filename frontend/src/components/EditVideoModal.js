// src/components/EditVideoModal.js - UPDATED
import React, { useState, useEffect } from "react";
import axios from "axios";

function EditVideoModal({ isOpen, onClose, video, onVideoUpdated, locations = [] }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [formData, setFormData] = useState({
    title: '',
    video_date: '',
    video_start_time: '',
    video_end_time: ''
  });

  // Initialize form when video changes
  useEffect(() => {
    if (video) {
      console.log("📝 Initializing edit form for video:", video);
      
      // Format date for input field (YYYY-MM-DD)
      const formatDate = (dateStr) => {
        if (!dateStr) return '';
        
        // If it's already in YYYY-MM-DD format
        if (dateStr.match(/^\d{4}-\d{2}-\d{2}$/)) {
          return dateStr;
        }
        
        // If it's a Date object or ISO string
        try {
          const date = new Date(dateStr);
          if (!isNaN(date.getTime())) {
            return date.toISOString().split('T')[0];
          }
        } catch (e) {
          console.warn("Could not parse date:", dateStr, e);
        }
        
        return '';
      };

      // Format time for input field (HH:MM)
      const formatTime = (timeStr) => {
        if (!timeStr) return '';
        
        // If it's already in HH:MM format
        if (timeStr.match(/^\d{1,2}:\d{2}$/)) {
          return timeStr;
        }
        
        // If it's in HH:MM:SS format
        if (timeStr.match(/^\d{1,2}:\d{2}:\d{2}$/)) {
          return timeStr.substring(0, 5);
        }
        
        // If it's an ISO time string
        if (timeStr.includes('T')) {
          const timePart = timeStr.split('T')[1];
          return timePart.substring(0, 5);
        }
        
        // If it's some other format
        const timeMatch = timeStr.match(/(\d{1,2}):(\d{2})/);
        if (timeMatch) {
          return `${timeMatch[1].padStart(2, '0')}:${timeMatch[2]}`;
        }
        
        return '';
      };

      setFormData({
        title: video.title || video.filename || '',
        video_date: formatDate(video.video_date),
        video_start_time: formatTime(video.start_time || video.video_start_time),
        video_end_time: formatTime(video.end_time || video.video_end_time)
      });
    }
  }, [video]);

  // Handle form input changes
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Handle time input (ensure HH:MM format)
  const handleTimeChange = (field, value) => {
    // Allow empty or valid time format
    if (value === '' || /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/.test(value)) {
      setFormData(prev => ({
        ...prev,
        [field]: value
      }));
    }
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!video?.id) {
      setError("No video selected for editing");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      console.log("📤 Submitting video update:", {
        videoId: video.id,
        formData,
        originalVideo: video
      });

      // Prepare update data
      const updateData = {};
      
      // Add title if changed
      if (formData.title !== (video.title || video.filename)) {
        updateData.title = formData.title;
      }
      
      // Add date if changed and valid
      if (formData.video_date && formData.video_date !== video.video_date) {
        updateData.video_date = formData.video_date;
      }
      
      // Add start time if changed and valid
      if (formData.video_start_time && formData.video_start_time !== (video.video_start_time || video.start_time)) {
        updateData.video_start_time = formData.video_start_time;
      }
      
      // Add end time if changed and valid
      if (formData.video_end_time && formData.video_end_time !== (video.video_end_time || video.end_time)) {
        updateData.video_end_time = formData.video_end_time;
      }

      // If nothing changed, show message and close
      if (Object.keys(updateData).length === 0) {
        setSuccess("No changes detected.");
        setTimeout(() => {
          onClose();
        }, 1500);
        return;
      }

      console.log("🔄 Sending update data:", updateData);

      // Make API call to update video metadata
      const response = await axios.put(
        `http://127.0.0.1:8000/api/videos/${video.id}/manage/`,
        updateData,
        {
          headers: {
            'Content-Type': 'application/json',
          }
        }
      );

      console.log("✅ Update response:", response.data);

      // Show success message
      setSuccess("Video metadata updated successfully!");
      
      // Close modal after delay and trigger refresh
      setTimeout(() => {
        onVideoUpdated(response.data.video || video);
      }, 1500);

    } catch (err) {
      console.error("❌ Error updating video:", err);
      
      let errorMessage = "Failed to update video metadata";
      if (err.response?.data?.error) {
        errorMessage = err.response.data.error;
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  // Handle video deletion
  const handleDelete = async () => {
    if (!video?.id) {
      setError("No video selected for deletion");
      return;
    }

    if (!window.confirm(`Are you sure you want to delete "${video.title || video.filename}"? This action cannot be undone.`)) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      console.log("🗑️ Deleting video:", video.id);
      
      const response = await axios.delete(
        `http://127.0.0.1:8000/api/videos/${video.id}/delete/`
      );

      console.log("✅ Delete response:", response.data);
      
      // Trigger refresh with delete flag
      onVideoUpdated({ ...video, _deleted: true });
      
    } catch (err) {
      console.error("❌ Error deleting video:", err);
      
      let errorMessage = "Failed to delete video";
      if (err.response?.data?.error) {
        errorMessage = err.response.data.error;
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
      setLoading(false);
    }
  };

  // Handle modal close
  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  // Don't render if not open or no video
  if (!isOpen || !video) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div 
        className="modal-content" 
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '500px' }}
      >
        {/* Modal Header */}
        <div className="modal-header" style={{ marginBottom: '20px' }}>
          <h2 style={{ margin: 0, fontSize: '24px', fontWeight: '600' }}>
            Edit Video Metadata
          </h2>
          <button 
            className="modal-close-button"
            onClick={handleClose}
            disabled={loading}
            style={{
              opacity: loading ? 0.5 : 1,
              cursor: loading ? 'not-allowed' : 'pointer'
            }}
          >
            ×
          </button>
        </div>

        {/* Success Message */}
        {success && (
          <div style={{
            backgroundColor: '#d1fae5',
            border: '1px solid #a7f3d0',
            color: '#065f46',
            padding: '12px 16px',
            borderRadius: '6px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span>✅</span>
            <span>{success}</span>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div style={{
            backgroundColor: '#fee2e2',
            border: '1px solid #fecaca',
            color: '#dc2626',
            padding: '12px 16px',
            borderRadius: '6px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <span>❌</span>
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Video Info */}
          <div style={{ marginBottom: '20px', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
            <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Original Filename</div>
            <div style={{ fontSize: '14px', fontWeight: '500', wordBreak: 'break-all' }}>
              {video.filename}
            </div>
            
            {video.processing_status && (
              <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  fontSize: '10px',
                  padding: '2px 6px',
                  borderRadius: '10px',
                  backgroundColor: video.processing_status === 'completed' ? '#10b981' : 
                                 video.processing_status === 'processing' ? '#f59e0b' : '#ef4444',
                  color: 'white',
                  textTransform: 'uppercase'
                }}>
                  {video.processing_status}
                </span>
                {video.vehicle_count > 0 && (
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>
                    • {video.vehicle_count} vehicles detected
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Title Field */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>
              Video Title
            </label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleInputChange}
              placeholder="Enter a descriptive title for this video"
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '14px',
                transition: 'border-color 0.2s'
              }}
              disabled={loading}
            />
            <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
              This is how the video will appear in lists
            </div>
          </div>

          {/* Date Field */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>
              Recording Date
            </label>
            <input
              type="date"
              name="video_date"
              value={formData.video_date}
              onChange={handleInputChange}
              max={new Date().toISOString().split('T')[0]}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '14px',
                transition: 'border-color 0.2s'
              }}
              disabled={loading}
            />
            <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
              When the video was recorded (YYYY-MM-DD)
            </div>
          </div>

          {/* Time Fields */}
          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', fontSize: '14px' }}>
              Recording Time
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>Start Time</div>
                <input
                  type="time"
                  value={formData.video_start_time}
                  onChange={(e) => handleTimeChange('video_start_time', e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    fontSize: '14px'
                  }}
                  disabled={loading}
                />
              </div>
              <div>
                <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>End Time</div>
                <input
                  type="time"
                  value={formData.video_end_time}
                  onChange={(e) => handleTimeChange('video_end_time', e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    fontSize: '14px'
                  }}
                  disabled={loading}
                />
              </div>
            </div>
            <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>
              Start and end times in 24-hour format (HH:MM)
            </div>
          </div>

          {/* Location Info (Read-only) */}
          {video.location && (
            <div style={{ 
              marginBottom: '24px', 
              padding: '12px', 
              backgroundColor: '#f0f9ff', 
              borderRadius: '6px',
              border: '1px solid #bae6fd'
            }}>
              <div style={{ fontSize: '12px', color: '#0369a1', marginBottom: '4px' }}>Processing Location</div>
              <div style={{ fontSize: '14px', fontWeight: '500', color: '#0369a1' }}>
                {video.location.display_name || video.location.name || 'Unknown'}
              </div>
              <div style={{ fontSize: '12px', color: '#0369a1', marginTop: '4px' }}>
                <em>Location cannot be changed after processing</em>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '32px' }}>
            {/* Delete Button */}
            <button
              type="button"
              onClick={handleDelete}
              disabled={loading}
              style={{
                padding: '10px 20px',
                border: '1px solid #ef4444',
                borderRadius: '6px',
                backgroundColor: 'white',
                color: '#ef4444',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontWeight: '500',
                fontSize: '14px',
                opacity: loading ? 0.5 : 1,
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => !loading && (e.currentTarget.style.backgroundColor = '#fef2f2')}
              onMouseLeave={(e) => !loading && (e.currentTarget.style.backgroundColor = 'white')}
            >
              {loading ? 'Deleting...' : 'Delete Video'}
            </button>

            {/* Save/Cancel Buttons */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="button"
                onClick={handleClose}
                disabled={loading}
                style={{
                  padding: '10px 20px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  backgroundColor: 'white',
                  color: '#4b5563',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontWeight: '500',
                  fontSize: '14px',
                  opacity: loading ? 0.5 : 1
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                style={{
                  padding: '10px 20px',
                  border: 'none',
                  borderRadius: '6px',
                  backgroundColor: loading ? '#93c5fd' : '#3b82f6',
                  color: 'white',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontWeight: '500',
                  fontSize: '14px',
                  transition: 'background-color 0.2s'
                }}
              >
                {loading ? (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      width: '16px',
                      height: '16px',
                      border: '2px solid rgba(255,255,255,0.3)',
                      borderTop: '2px solid white',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite'
                    }}></span>
                    Saving...
                  </span>
                ) : 'Save Changes'}
              </button>
            </div>
          </div>

          {/* Help Text */}
          <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: '12px', color: '#6b7280', textAlign: 'center' }}>
              Changes will update the video's grouping and reporting
            </div>
          </div>
        </form>
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        input[type="date"]::-webkit-calendar-picker-indicator,
        input[type="time"]::-webkit-calendar-picker-indicator {
          cursor: pointer;
          opacity: 0.6;
        }
        
        input[type="date"]:hover,
        input[type="time"]:hover,
        input[type="text"]:hover {
          border-color: #9ca3af;
        }
        
        input[type="date"]:focus,
        input[type="time"]:focus,
        input[type="text"]:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        
        input:disabled {
          background-color: #f3f4f6;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}

export default EditVideoModal;