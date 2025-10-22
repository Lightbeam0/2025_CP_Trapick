// src/components/VideoUploadModal.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const VideoUploadModal = ({ isOpen, onClose, onUpload }) => {
  // Consolidated form state
  const [formData, setFormData] = useState({
    file: null,
    title: '',
    locationId: '',
    videoDate: '',
    startTime: '',
    endTime: '',
    sessionId: ''
  });

  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [currentProgress, setCurrentProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadId, setUploadId] = useState(null);
  const [websocketConnected, setWebsocketConnected] = useState(false);
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [loadingLocations, setLoadingLocations] = useState(false);
  
  // Session selection state
  const [sessionOptions, setSessionOptions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(false);

  // Helper to update form fields
  const updateFormField = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  // Load locations and sessions when modal opens
  useEffect(() => {
    if (isOpen) {
      fetchLocations();
      fetchSessionsForUpload();
    }
  }, [isOpen]);

  const fetchLocations = async () => {
    try {
      setLoadingLocations(true);
      console.log("🔄 Fetching locations for upload modal...");
      const response = await axios.get('http://127.0.0.1:8000/api/locations/');
      console.log("✅ Locations loaded for upload:", response.data);
      setLocations(response.data);
    } catch (error) {
      console.error('Error fetching locations:', error);
    } finally {
      setLoadingLocations(false);
    }
  };

  // Fetch available sessions for upload
  const fetchSessionsForUpload = async () => {
    try {
      setLoadingSessions(true);
      console.log("🔄 Fetching sessions for upload dropdown...");
      const response = await axios.get('http://127.0.0.1:8000/api/sessions/');
      // Filter sessions based on status if needed
      const filteredSessions = response.data.filter(session => session.status === 'pending_upload' || session.status === 'completed');
      console.log("✅ Sessions loaded for upload:", filteredSessions);
      setSessionOptions(filteredSessions);
    } catch (error) {
      console.error('Error fetching sessions for upload:', error);
      setSessionOptions([]);
    } finally {
      setLoadingSessions(false);
    }
  };

  // Update selected location when locationId changes
  useEffect(() => {
    if (formData.locationId) {
      const location = locations.find(loc => loc.id === parseInt(formData.locationId));
      setSelectedLocation(location);
    } else {
      setSelectedLocation(null);
    }
  }, [formData.locationId, locations]);

  // Auto-fill date/time from filename if possible
  useEffect(() => {
    if (formData.file) {
      const filename = formData.file.name.toLowerCase();
      
      // Only auto-fill if fields are empty
      if (!formData.videoDate) {
        const dateMatch = filename.match(/(\d{4}[-_]\d{2}[-_]\d{2})|(\d{2}[-_]\d{2}[-_]\d{4})/);
        if (dateMatch) {
          const dateStr = dateMatch[0].replace(/_/g, '-');
          updateFormField('videoDate', dateStr);
        }
      }
      
      if (!formData.startTime || !formData.endTime) {
        const timeMatch = filename.match(/(\d{1,2}[-_:]\d{2})[-_:]?(\d{1,2}[-_:]\d{2})?/);
        if (timeMatch) {
          if (timeMatch[1] && !formData.startTime) updateFormField('startTime', timeMatch[1].replace(/_/g, ':'));
          if (timeMatch[2] && !formData.endTime) updateFormField('endTime', timeMatch[2].replace(/_/g, ':'));
        }
      }
      
      if (!formData.title) {
        const cleanName = formData.file.name.replace(/\.[^/.]+$/, "");
        updateFormField('title', cleanName);
      }
    }
  }, [formData.file]);

  // Progress tracking with WebSocket fallback
  useEffect(() => {
    let ws;
    let intervalId;
    
    const startPollingProgress = () => {
      intervalId = setInterval(async () => {
        try {
          const response = await axios.get(`http://127.0.0.1:8000/api/progress/${uploadId}/`);
          const progressData = response.data;
          
          console.log(`📊 Polling progress: ${progressData.progress}% - ${progressData.message}`);
          
          setCurrentProgress(progressData.progress || 0);
          setProgressMessage(progressData.message || '');
          
          if (progressData.progress === 100) {
            console.log("✅ Processing completed via polling");
            handleProcessingComplete();
            clearInterval(intervalId);
          }
        } catch (error) {
          console.error('Error fetching progress:', error);
        }
      }, 2000);
    };
    
    const handleProcessingComplete = () => {
      setIsProcessing(false);
      setUploading(false);
      setProgressMessage('Processing completed!');
      
      if (onUpload) {
        onUpload({ upload_id: uploadId, status: 'completed', session_id: formData.sessionId });
      }
    };
    
    if (isProcessing && uploadId) {
      console.log(`🔄 Starting progress tracking for: ${uploadId}`);
      
      try {
        // Try WebSocket first
        ws = new WebSocket(`ws://127.0.0.1:8000/ws/video-progress/${uploadId}/`);
        
        ws.onopen = () => {
          console.log('✅ WebSocket connected for progress updates');
          setWebsocketConnected(true);
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log(`📡 WebSocket progress: ${data.progress}% - ${data.message}`);
            
            setCurrentProgress(data.progress || 0);
            setProgressMessage(data.message || '');
            
            if (data.progress === 100) {
              console.log("✅ Processing completed via WebSocket");
              handleProcessingComplete();
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };
        
        ws.onerror = (error) => {
          console.error('❌ WebSocket error:', error);
          setWebsocketConnected(false);
          // Fallback to polling if WebSocket fails
          startPollingProgress();
        };
        
        ws.onclose = () => {
          console.log('🔌 WebSocket disconnected');
          setWebsocketConnected(false);
        };
        
      } catch (error) {
        console.error('WebSocket connection failed, using polling:', error);
        startPollingProgress();
      }
    }
    
    return () => {
      if (ws) ws.close();
      if (intervalId) clearInterval(intervalId);
    };
  }, [isProcessing, uploadId, onUpload, formData.sessionId]);

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
      
      updateFormField('file', file);
      
      // Use functional update to ensure we get the latest state for title
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
    console.log('Selected file:', formData.file?.name);
    console.log('Location ID:', formData.locationId);
    console.log('Video date:', formData.videoDate);
    console.log('Selected session ID:', formData.sessionId);

    if (!formData.file) {
      alert('Please select a video file first!');
      return;
    }

    if (!formData.videoDate) {
      alert('Please specify the video recording date');
      return;
    }

    setUploading(true);
    setIsProcessing(true);
    setUploadResult(null);
    setCurrentProgress(0);
    setProgressMessage('Starting upload...');

    const uploadFormData = new FormData();
    uploadFormData.append('video', formData.file);
    uploadFormData.append('title', formData.title);
    uploadFormData.append('video_date', formData.videoDate);
    if (formData.startTime) uploadFormData.append('start_time', formData.startTime);
    if (formData.endTime) uploadFormData.append('end_time', formData.endTime);
    if (formData.locationId) uploadFormData.append('location_id', formData.locationId);
    if (formData.sessionId) {
        uploadFormData.append('session_id', formData.sessionId);
    }

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
            console.log(`📤 Upload progress: ${progress}%`);
          }
        }
      });
      
      console.log('✅ Upload response:', response.data);
      
      setUploadId(response.data.upload_id);
      setUploadResult({ success: true, data: response.data });
      
      const message = formData.sessionId
        ? 'Upload complete! Video added to session. Session processing will start after all videos are uploaded.'
        : 'Upload complete! Starting video analysis...';
      
      setProgressMessage(message);
      setCurrentProgress(formData.sessionId ? 15 : 15);

      if (onUpload) {
         onUpload({ upload_id: response.data.upload_id, status: 'uploaded', session_id: formData.sessionId });
      }
      
    } catch (error) {
      console.error('🔴 UPLOAD ERROR:', error);
      console.error('Error response:', error.response);
      
      const errorMessage = error.response?.data?.error || error.message || 'Upload failed';
      setUploadResult({ success: false, error: errorMessage });
      setUploading(false);
      setIsProcessing(false);
      setProgressMessage('Upload failed!');
    }
  };

  const handleClose = () => {
    // Reset all state
    setFormData({
      file: null,
      title: '',
      locationId: '',
      videoDate: '',
      startTime: '',
      endTime: '',
      sessionId: ''
    });
    setUploading(false);
    setIsProcessing(false);
    setUploadResult(null);
    setCurrentProgress(0);
    setProgressMessage('');
    setUploadId(null);
    setWebsocketConnected(false);
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
              <span style={{ color: websocketConnected ? '#10b981' : '#ef4444' }}>
                {websocketConnected ? '🟢 Live' : '🔴 Polling'}
              </span>
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
        
        {/* Session Selection Dropdown */}
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Associate with Analysis Session (Optional)
          </label>
          <select
            value={formData.sessionId}
            onChange={(e) => updateFormField('sessionId', e.target.value)}
            style={{
              width: '100%',
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              backgroundColor: 'white'
            }}
            disabled={uploading || isProcessing || loadingSessions}
          >
            <option value="">Process Individually</option>
            {loadingSessions ? (
              <option disabled>Loading sessions...</option>
            ) : (
              sessionOptions.map(session => (
                <option key={session.id} value={session.id}>
                  {session.name} - {session.location_details?.display_name || session.location} ({session.status})
                </option>
              ))
            )}
          </select>
          <p style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
            Select an existing session to group this video with others for combined analysis.
          </p>
        </div>
        
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
              borderRadius: '4px',
              backgroundColor: 'white'
            }}
            disabled={uploading || isProcessing || loadingLocations}
          >
            <option value="">Select a location</option>
            {loadingLocations ? (
              <option disabled>Loading locations...</option>
            ) : (
              locations.map(location => (
                <option key={location.id} value={location.id}>
                  {location.display_name} - {location.processing_profile_display}
                </option>
              ))
            )}
          </select>
        </div>
        
        {/* Result Display */}
        {uploadResult && !isProcessing && (
          <div style={{
            marginBottom: '16px',
            padding: '12px',
            borderRadius: '4px',
            backgroundColor: uploadResult.success ? '#f0fff4' : '#fee2e2',
            border: `1px solid ${uploadResult.success ? '#10b981' : '#ef4444'}`,
            color: uploadResult.success ? '#065f46' : '#991b1b'
          }}>
            {uploadResult.success ? (
              <div>
                <strong>✓ Upload Successful!</strong>
                <p style={{ margin: '8px 0 0 0', fontSize: '14px' }}>
                  {formData.sessionId 
                    ? 'Video added to session. Session processing will start after all videos are uploaded.'
                    : 'Video is being processed. You can check the analysis results shortly.'
                  }
                </p>
              </div>
            ) : (
              <div>
                <strong>❌ Upload Failed</strong>
                <p style={{ margin: '8px 0 0 0', fontSize: '14px' }}>
                  {uploadResult.error}
                </p>
              </div>
            )}
          </div>
        )}
        
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
            disabled={!formData.file || uploading || isProcessing}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '4px',
              backgroundColor: (uploading || isProcessing) ? '#9ca3af' : '#3b82f6',
              color: 'white',
              cursor: (!formData.file || uploading || isProcessing) ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              opacity: (!formData.file || uploading || isProcessing) ? 0.6 : 1
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