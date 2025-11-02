// src/components/VideoUploadModal.js - SIMPLIFIED FOR NEW APPROACH
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const VideoUploadModal = ({ isOpen, onClose, onUpload }) => {
  const [formData, setFormData] = useState({
    file: null,
    title: '',
    locationId: '',
    videoDate: '',
    startTime: '',
    endTime: ''
  });

  const [uploading, setUploading] = useState(false);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadId, setUploadId] = useState(null);
  const [locations, setLocations] = useState([]);
  const [loadingLocations, setLoadingLocations] = useState(false);

  const updateFormField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  useEffect(() => {
    if (isOpen) {
      fetchLocations();
    }
  }, [isOpen]);

  const fetchLocations = async () => {
    try {
      setLoadingLocations(true);
      const response = await axios.get('http://127.0.0.1:8000/api/locations/');
      setLocations(response.data);
    } catch (error) {
      console.error('Error fetching locations:', error);
    } finally {
      setLoadingLocations(false);
    }
  };

  useEffect(() => {
    if (formData.file) {
      const filename = formData.file.name.toLowerCase();
      
      if (!formData.videoDate) {
        const dateMatch = filename.match(/(\d{4}[-_]\d{2}[-_]\d{2})|(\d{2}[-_]\d{2}[-_]\d{4})/);
        if (dateMatch) {
          const dateStr = dateMatch[0].replace(/_/g, '-');
          updateFormField('videoDate', dateStr);
        }
      }
      
      if (!formData.title) {
        const cleanName = formData.file.name.replace(/\.[^/.]+$/, "");
        updateFormField('title', cleanName);
      }
    }
  }, [formData.file]);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const validTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/webm', 'video/quicktime'];
      if (!validTypes.includes(file.type)) {
        alert('Please select a valid video file (MP4, AVI, MOV, WebM)');
        return;
      }
      
      const maxSize = 2 * 1024 * 1024 * 1024; // 2GB
      if (file.size > maxSize) {
        alert(`File size must be less than 2GB. Your file is ${(file.size / (1024 * 1024 * 1024)).toFixed(2)}GB`);
        return;
      }
      
      setFormData(prev => {
        if (!prev.title) {
          const filename = file.name.replace(/\.[^/.]+$/, "");
          return { ...prev, file, title: filename };
        }
        return { ...prev, file };
      });
    }
  };

  const handleUpload = async () => {
    console.log('🚀 Starting upload process...');

    if (!formData.file) {
      alert('Please select a video file first!');
      return;
    }

    if (!formData.videoDate) {
      alert('Please specify the video recording date');
      return;
    }

    if (!formData.locationId) {
      alert('Please select a location');
      return;
    }

    setUploading(true);
    setIsProcessing(true);
    setCurrentProgress(0);
    setProgressMessage('Starting upload...');

    const uploadFormData = new FormData();
    uploadFormData.append('video', formData.file);
    uploadFormData.append('title', formData.title);
    uploadFormData.append('video_date', formData.videoDate);
    uploadFormData.append('location_id', formData.locationId);
    if (formData.startTime) uploadFormData.append('start_time', formData.startTime);
    if (formData.endTime) uploadFormData.append('end_time', formData.endTime);

    try {
      const response = await axios.post('http://127.0.0.1:8000/api/upload/video/', uploadFormData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 30000,
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setCurrentProgress(progress);
            setProgressMessage(`Uploading: ${progress}%`);
          }
        }
      });
      
      setUploadId(response.data.upload_id);
      setProgressMessage('Upload complete! Starting video analysis...');
      setCurrentProgress(15);

      if (onUpload) {
        onUpload({ upload_id: response.data.upload_id, status: 'uploaded' });
      }
      
    } catch (error) {
      console.error('🔴 UPLOAD ERROR:', error);
      alert(`Upload failed: ${error.response?.data?.error || error.message}`);
      setUploading(false);
      setIsProcessing(false);
      setProgressMessage('Upload failed!');
    }
  };

  const handleClose = () => {
    setFormData({
      file: null,
      title: '',
      locationId: '',
      videoDate: '',
      startTime: '',
      endTime: ''
    });
    setUploading(false);
    setIsProcessing(false);
    setCurrentProgress(0);
    setProgressMessage('');
    setUploadId(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        padding: '24px',
        width: '90%',
        maxWidth: '500px',
        maxHeight: '90vh',
        overflow: 'auto'
      }}>
        <h2 style={{ marginBottom: '16px', fontSize: '24px', fontWeight: '600' }}>
          Upload Traffic Video
        </h2>
        
        {/* Progress Bar */}
        {(uploading || isProcessing) && (
          <div style={{ marginBottom: '16px' }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginBottom: '8px',
              fontSize: '14px'
            }}>
              <span>Progress: {currentProgress}%</span>
            </div>
            <div style={{
              width: '100%',
              height: '20px',
              backgroundColor: '#e5e7eb',
              borderRadius: '10px',
              overflow: 'hidden'
            }}>
              <div style={{
                width: `${currentProgress}%`,
                height: '100%',
                backgroundColor: currentProgress === 100 ? '#10b981' : '#3b82f6',
                transition: 'width 0.3s ease',
                borderRadius: '10px'
              }}></div>
            </div>
            {progressMessage && (
              <div style={{
                marginTop: '8px',
                fontSize: '12px',
                color: '#6b7280',
                textAlign: 'center'
              }}>
                {progressMessage}
              </div>
            )}
          </div>
        )}
        
        {/* File Input */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Video File *
          </label>
          <input 
            type="file" 
            accept="video/*" 
            onChange={handleFileChange}
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px'
            }}
            disabled={uploading || isProcessing}
          />
          {formData.file && (
            <p style={{ marginTop: '8px', fontSize: '14px', color: '#666' }}>
              Selected: {formData.file.name} ({(formData.file.size / 1024 / 1024).toFixed(2)} MB)
            </p>
          )}
        </div>
        
        {/* Title Input */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Video Title
          </label>
          <input 
            type="text" 
            value={formData.title}
            onChange={(e) => updateFormField('title', e.target.value)}
            placeholder="Enter a title for this video"
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px'
            }}
            disabled={uploading || isProcessing}
          />
        </div>
        
        {/* Date Input */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Video Recording Date *
          </label>
          <input 
            type="date" 
            value={formData.videoDate}
            onChange={(e) => updateFormField('videoDate', e.target.value)}
            required
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px'
            }}
            disabled={uploading || isProcessing}
          />
        </div>

        {/* Time Inputs */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
              Start Time
            </label>
            <input 
              type="time" 
              value={formData.startTime}
              onChange={(e) => updateFormField('startTime', e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                borderRadius: '4px'
              }}
              disabled={uploading || isProcessing}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
              End Time
            </label>
            <input 
              type="time" 
              value={formData.endTime}
              onChange={(e) => updateFormField('endTime', e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                border: '1px solid #ddd',
                borderRadius: '4px'
              }}
              disabled={uploading || isProcessing}
            />
          </div>
        </div>
        
        {/* Location Selection */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Location *
          </label>
          <select 
            value={formData.locationId}
            onChange={(e) => updateFormField('locationId', e.target.value)}
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px'
            }}
            disabled={uploading || isProcessing || loadingLocations}
          >
            <option value="">Select a location</option>
            {loadingLocations ? (
              <option disabled>Loading locations...</option>
            ) : (
              locations.map(location => (
                <option key={location.id} value={location.id}>
                  {location.display_name}
                </option>
              ))
            )}
          </select>
        </div>
        
        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button 
            onClick={handleClose}
            style={{
              padding: '10px 20px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              backgroundColor: 'white',
              color: '#374151',
              cursor: (uploading || isProcessing) ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              opacity: (uploading || isProcessing) ? 0.6 : 1
            }}
            disabled={uploading || isProcessing}
          >
            {isProcessing ? 'Close' : 'Cancel'}
          </button>
          <button 
            onClick={handleUpload}
            disabled={!formData.file || uploading || isProcessing || !formData.locationId}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '4px',
              backgroundColor: (!formData.file || uploading || isProcessing || !formData.locationId) ? '#9ca3af' : '#3b82f6',
              color: 'white',
              cursor: (!formData.file || uploading || isProcessing || !formData.locationId) ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              opacity: (!formData.file || uploading || isProcessing || !formData.locationId) ? 0.6 : 1
            }}
          >
            {isProcessing ? 'Processing...' : uploading ? 'Uploading...' : 'Upload Video'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default VideoUploadModal;