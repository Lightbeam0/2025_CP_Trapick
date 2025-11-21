// src/components/VideoUploadModal.js
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
  const [taskId, setTaskId] = useState(null);
  const [locations, setLocations] = useState([]);
  const [loadingLocations, setLoadingLocations] = useState(false);
  // Add state for success message and auto-close
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [error, setError] = useState('');

  const updateFormField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  useEffect(() => {
    if (isOpen) {
      fetchLocations();
      // Reset all states when modal opens
      setUploadSuccess(false);
      setSuccessMessage('');
      setError('');
      setFormData({
        file: null,
        title: '',
        locationId: '',
        videoDate: '',
        startTime: '',
        endTime: ''
      });
    }
  }, [isOpen]);

  const fetchLocations = async () => {
    try {
      setLoadingLocations(true);
      const response = await axios.get('http://127.0.0.1:8000/api/locations/');
      setLocations(response.data);
    } catch (error) {
      console.error('Error fetching locations:', error);
      setError('Failed to load locations.');
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
        setError('Please select a valid video file (MP4, AVI, MOV, WebM)');
        setFormData(prev => ({ ...prev, file: null }));
        return;
      }

      const maxSize = 2 * 1024 * 1024 * 1024; // 2GB
      if (file.size > maxSize) {
        setError(`File size must be less than 2GB. Your file is ${(file.size / (1024 * 1024 * 1024)).toFixed(2)}GB`);
        setFormData(prev => ({ ...prev, file: null }));
        return;
      }

      setFormData(prev => {
        if (!prev.title) {
          const filename = file.name.replace(/\.[^/.]+$/, "");
          return { ...prev, file, title: filename };
        }
        return { ...prev, file };
      });
      setError(''); // Clear error when a valid file is selected
    }
  };

  const handleUpload = async () => {
    console.log('🚀 Starting upload process...');

    if (!formData.file) {
      setError('Please select a video file first!');
      return;
    }

    if (!formData.videoDate) {
      setError('Please specify the video recording date');
      return;
    }

    if (!formData.locationId) {
      setError('Please select a location');
      return;
    }

    setError(''); // Clear any previous errors
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

      const videoId = response.data.upload_id;
      const taskId = response.data.task_id; // Capture task ID if needed later
      setUploadId(videoId);
      setTaskId(taskId);
      setProgressMessage('Upload complete! Starting video analysis...');
      setCurrentProgress(15); // Or keep at 100% if you consider upload complete here

      // --- CRITICAL: Call the parent's onUpload callback ---
      // This tells the Sidebar to add the video to its processing list
      if (onUpload) {
        onUpload({ upload_id: videoId, task_id: taskId, status: 'uploaded', video_info: response.data.video_info });
      }

      // --- CRITICAL: Set success state and trigger auto-close ---
      setUploadSuccess(true);
      setSuccessMessage(response.data.message || 'Video uploaded and processing started successfully!');

      // Auto-close after 2 seconds if successful
      setTimeout(() => {
        handleClose(); // This will reset states and call onClose
      }, 2000); // 2 seconds delay

      // Optionally, poll for final status if needed within the modal,
      // but the sidebar should handle ongoing progress.
      // const finalStatus = await pollForFinalStatus(videoId);

    } catch (error) {
      console.error('🔴 UPLOAD ERROR:', error);
      const errorMessage = error.response?.data?.error || error.message;
      setError(`Upload failed: ${errorMessage}`);
      setUploading(false);
      setIsProcessing(false);
      setProgressMessage('Upload failed!');
    }
  };

  const handleClose = () => {
    // Reset all states
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
    setTaskId(null);
    setUploadSuccess(false); // Reset success state
    setSuccessMessage('');
    setError('');
    onClose(); // Call the parent's onClose function
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div className="modal-header">
            <h2 className="modal-title">Upload Traffic Video</h2>
            <button className="modal-close-button" onClick={handleClose}>
                ×
            </button>
        </div>

        {/* Display Success Message */}
        {uploadSuccess && (
          <div className="alert-success">
            <span className="alert-icon">✅</span>
            <span>{successMessage}</span>
          </div>
        )}

        {/* Display Error Message */}
        {error && !uploadSuccess && (
          <div className="alert-error">
            {error}
          </div>
        )}

        {/* Progress Bar - Show during upload and initial processing handoff */}
        {(uploading || isProcessing) && !uploadSuccess && (
          <div className="upload-progress-section">
            <div className="progress-info">
              <span>Progress: {currentProgress}%</span>
            </div>
            <div className="progress-bar-container">
              <div
                className="progress-bar-fill"
                style={{ width: `${currentProgress}%` }}
              ></div>
            </div>
            {progressMessage && (
              <div className="progress-message">
                {progressMessage}
              </div>
            )}
          </div>
        )}

        {/* Form Content - Hide if successful */}
        {!uploadSuccess && (
          <>
            {/* File Input */}
            <div className="form-group">
              <label className="form-label">Video File *</label>
              <input
                type="file"
                accept="video/*"
                onChange={handleFileChange}
                className="form-input"
                disabled={uploading || isProcessing}
              />
              {formData.file && (
                <p className="file-info">
                  Selected: {formData.file.name} ({(formData.file.size / 1024 / 1024).toFixed(2)} MB)
                </p>
              )}
            </div>

            {/* Title Input */}
            <div className="form-group">
              <label className="form-label">Video Title</label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => updateFormField('title', e.target.value)}
                placeholder="Enter a title for this video"
                className="form-input"
                disabled={uploading || isProcessing}
              />
            </div>

            {/* Date Input */}
            <div className="form-group">
              <label className="form-label">Video Recording Date *</label>
              <input
                type="date"
                value={formData.videoDate}
                onChange={(e) => updateFormField('videoDate', e.target.value)}
                required
                className="form-input"
                disabled={uploading || isProcessing}
              />
            </div>

            {/* Time Inputs */}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Start Time</label>
                <input
                  type="time"
                  value={formData.startTime}
                  onChange={(e) => updateFormField('startTime', e.target.value)}
                  className="form-input"
                  disabled={uploading || isProcessing}
                />
              </div>
              <div className="form-group">
                <label className="form-label">End Time</label>
                <input
                  type="time"
                  value={formData.endTime}
                  onChange={(e) => updateFormField('endTime', e.target.value)}
                  className="form-input"
                  disabled={uploading || isProcessing}
                />
              </div>
            </div>

            {/* Location Selection */}
            <div className="form-group">
              <label className="form-label">Location *</label>
              <select
                value={formData.locationId}
                onChange={(e) => updateFormField('locationId', e.target.value)}
                className="form-input"
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
            <div className="modal-actions">
              <button
                onClick={handleClose}
                className="button button-secondary"
                disabled={uploading || isProcessing}
              >
                {isProcessing ? 'Processing...' : 'Cancel'}
              </button>
              <button
                onClick={handleUpload}
                disabled={!formData.file || uploading || isProcessing || !formData.locationId}
                className="button button-primary"
              >
                {isProcessing ? 'Processing...' : uploading ? 'Uploading...' : 'Upload Video'}
              </button>
            </div>
          </>
        )}

        {/* Auto-Close Message */}
        {uploadSuccess && (
          <div className="auto-close-message">
            <p>Modal will close automatically...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default VideoUploadModal;