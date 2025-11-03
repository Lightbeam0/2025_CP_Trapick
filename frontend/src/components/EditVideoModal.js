// src/components/EditVideoModal.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const EditVideoModal = ({ isOpen, onClose, video, onVideoUpdated, locations }) => {
  const [formData, setFormData] = useState({
    title: '',
    video_date: '',
    video_start_time: '',
    video_end_time: '',
    location_id: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && video) {
      // Populate form with current video data
      setFormData({
        title: video.title || video.filename || '',
        video_date: video.video_date || '',
        video_start_time: video.video_start_time || '',
        video_end_time: video.video_end_time || '',
        location_id: video.location?.id || ''
      });
      setError('');
    }
  }, [isOpen, video]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!video) {
      setError('No video selected');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.put(
        `http://127.0.0.1:8000/api/videos/${video.id}/manage/`,
        formData
      );

      if (onVideoUpdated) {
        onVideoUpdated(response.data.video);
      }

      onClose();
      
    } catch (err) {
      console.error('Error updating video:', err);
      setError(err.response?.data?.error || 'Failed to update video');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!video) return;
    
    if (!window.confirm(`Are you sure you want to delete "${video.title || video.filename}"? This action cannot be undone.`)) {
      return;
    }

    setLoading(true);

    try {
      await axios.delete(`http://127.0.0.1:8000/api/videos/${video.id}/delete/`);
      
      if (onVideoUpdated) {
        onVideoUpdated(null); // Signal that video was deleted
      }
      
      onClose();
      
    } catch (err) {
      console.error('Error deleting video:', err);
      setError(err.response?.data?.error || 'Failed to delete video');
      setLoading(false);
    }
  };

  if (!isOpen || !video) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
        <div className="modal-header">
          <h2 style={{ margin: '0 0 16px 0', color: '#2d3748' }}>
            Edit Video: {video.filename}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              cursor: 'pointer',
              color: '#666',
              position: 'absolute',
              top: '16px',
              right: '16px'
            }}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{
              backgroundColor: '#fee2e2',
              border: '1px solid #fecaca',
              color: '#dc2626',
              padding: '12px',
              borderRadius: '6px',
              marginBottom: '16px',
              fontSize: '14px'
            }}>
              {error}
            </div>
          )}

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>
              Video Title
            </label>
            <input
              type="text"
              value={formData.title}
              onChange={(e) => handleInputChange('title', e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '14px'
              }}
              placeholder="Enter video title"
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>
              Recording Date *
            </label>
            <input
              type="date"
              value={formData.video_date}
              onChange={(e) => handleInputChange('video_date', e.target.value)}
              required
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '14px'
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>
                Start Time
              </label>
              <input
                type="time"
                value={formData.video_start_time}
                onChange={(e) => handleInputChange('video_start_time', e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>
                End Time
              </label>
              <input
                type="time"
                value={formData.video_end_time}
                onChange={(e) => handleInputChange('video_end_time', e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  fontSize: '14px'
                }}
              />
            </div>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>
              Location
            </label>
            <select
              value={formData.location_id}
              onChange={(e) => handleInputChange('location_id', e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '14px'
              }}
            >
              <option value="">Select a location</option>
              {locations.map(location => (
                <option key={location.id} value={location.id}>
                  {location.display_name}
                </option>
              ))}
            </select>
          </div>

          <div style={{ 
            display: 'flex', 
            gap: '12px', 
            justifyContent: 'space-between',
            borderTop: '1px solid #e5e7eb',
            paddingTop: '16px'
          }}>
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
                fontSize: '14px',
                fontWeight: '500'
              }}
            >
              {loading ? 'Deleting...' : 'Delete Video'}
            </button>
            
            <div style={{ display: 'flex', gap: '12px' }}>
              <button
                type="button"
                onClick={onClose}
                disabled={loading}
                style={{
                  padding: '10px 20px',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  backgroundColor: 'white',
                  color: '#374151',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
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
                  backgroundColor: loading ? '#9ca3af' : '#3b82f6',
                  color: 'white',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                {loading ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{
                      width: '16px',
                      height: '16px',
                      border: '2px solid transparent',
                      borderTop: '2px solid white',
                      borderRadius: '50%',
                      animation: 'spin 1s linear infinite'
                    }}></div>
                    Saving...
                  </div>
                ) : (
                  'Save Changes'
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default EditVideoModal;