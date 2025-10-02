import React, { useState, useEffect } from 'react';
import axios from 'axios';

const VideoUploadModal = ({ isOpen, onClose, onUpload }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [title, setTitle] = useState('');
  const [locationId, setLocationId] = useState('');
  const [currentProgress, setCurrentProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadId, setUploadId] = useState(null);
  const [websocketConnected, setWebsocketConnected] = useState(false);
  const [locations, setLocations] = useState([]);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [loadingLocations, setLoadingLocations] = useState(false);
  
  const [videoDate, setVideoDate] = useState('');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');

  // Load locations when modal opens
  useEffect(() => {
    if (isOpen) {
      fetchLocations();
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

  // Update selected location when locationId changes
  useEffect(() => {
    if (locationId) {
      const location = locations.find(loc => loc.id === parseInt(locationId));
      setSelectedLocation(location);
    } else {
      setSelectedLocation(null);
    }
  }, [locationId, locations]);

  // Auto-fill date/time from filename if possible
  useEffect(() => {
    if (selectedFile) {
      const filename = selectedFile.name.toLowerCase();
      
      const dateMatch = filename.match(/(\d{4}[-_]\d{2}[-_]\d{2})|(\d{2}[-_]\d{2}[-_]\d{4})/);
      if (dateMatch) {
        const dateStr = dateMatch[0].replace(/_/g, '-');
        setVideoDate(dateStr);
      }
      
      const timeMatch = filename.match(/(\d{1,2}[-_:]\d{2})[-_:]?(\d{1,2}[-_:]\d{2})?/);
      if (timeMatch) {
        if (timeMatch[1]) setStartTime(timeMatch[1].replace(/_/g, ':'));
        if (timeMatch[2]) setEndTime(timeMatch[2].replace(/_/g, ':'));
      }
      
      if (!title) {
        const cleanName = selectedFile.name.replace(/\.[^/.]+$/, "");
        setTitle(cleanName);
      }
    }
  }, [selectedFile, title]);

  // ✅ FIXED: Progress polling when processing
  useEffect(() => {
    let intervalId;
    
    if (isProcessing && uploadId) {
      console.log(`🔄 Starting progress polling for: ${uploadId}`);
      intervalId = setInterval(async () => {
        try {
          // ✅ FIXED: Use correct API endpoint
          const response = await axios.get(`http://127.0.0.1:8000/api/progress/${uploadId}/`);
          const progressData = response.data;
          
          console.log(`📊 Progress update: ${progressData.progress}% - ${progressData.message}`);
          
          setCurrentProgress(progressData.progress || 0);
          setProgressMessage(progressData.message || '');
          
          // If progress is 100%, processing is complete
          if (progressData.progress === 100) {
            console.log("✅ Processing completed via polling");
            setIsProcessing(false);
            setUploading(false);
            setProgressMessage('Processing completed!');
            
            if (onUpload) {
              onUpload({ upload_id: uploadId, status: 'completed' });
            }
            
            clearInterval(intervalId);
          }
        } catch (error) {
          console.error('Error fetching progress:', error);
        }
      }, 2000);
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isProcessing, uploadId, onUpload]);

  // ✅ FIXED: WebSocket for real-time updates
  useEffect(() => {
    let ws;
    
    if (isProcessing && uploadId) {
      console.log(`🔌 Connecting WebSocket for: ${uploadId}`);
      
      // ✅ FIXED: Correct WebSocket URL
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
            setIsProcessing(false);
            setUploading(false);
            setProgressMessage('Processing completed!');
            
            if (onUpload) {
              onUpload({ upload_id: uploadId, status: 'completed' });
            }
            
            ws.close();
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setWebsocketConnected(false);
      };
      
      ws.onclose = () => {
        console.log('🔌 WebSocket disconnected');
        setWebsocketConnected(false);
      };
    }
    
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [isProcessing, uploadId, onUpload]);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const validTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/webm', 'video/quicktime'];
      if (!validTypes.includes(file.type)) {
        alert('Please select a valid video file (MP4, AVI, MOV, WebM)');
        return;
      }
      
      if (file.size > 500 * 1024 * 1024) {
        alert('File size must be less than 500MB');
        return;
      }
      
      setSelectedFile(file);
      if (!title) {
        const filename = file.name.replace(/\.[^/.]+$/, "");
        setTitle(filename);
      }
    }
  };

  const handleUpload = async () => {
    console.log('🚀 Starting upload process...');
    console.log('Selected file:', selectedFile?.name);
    console.log('Location ID:', locationId);
    console.log('Video date:', videoDate);

    if (!selectedFile) {
      alert('Please select a video file first!');
      return;
    }

    if (!videoDate) {
      alert('Please specify the video recording date');
      return;
    }

    setUploading(true);
    setIsProcessing(true);
    setUploadResult(null);
    setCurrentProgress(0);
    setProgressMessage('Starting upload...');

    const formData = new FormData();
    formData.append('video', selectedFile);
    formData.append('title', title);
    formData.append('video_date', videoDate);
    if (startTime) formData.append('start_time', startTime);
    if (endTime) formData.append('end_time', endTime);
    if (locationId) formData.append('location_id', locationId);

    try {
      // ✅ FIXED: Use correct API endpoint
      const response = await axios.post('http://127.0.0.1:8000/api/upload/video/', formData, {
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
      setProgressMessage('Upload complete! Starting video analysis...');
      setCurrentProgress(15); // Move to processing stage
      
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
    setSelectedFile(null);
    setUploading(false);
    setIsProcessing(false);
    setUploadResult(null);
    setCurrentProgress(0);
    setProgressMessage('');
    setTitle('');
    setLocationId('');
    setVideoDate('');
    setStartTime('');
    setEndTime('');
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
        
        {/* Rest of your form remains the same */}
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
          {selectedFile && (
            <p style={{ marginTop: '8px', fontSize: '14px', color: '#666' }}>
              Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
            </p>
          )}
        </div>
        
        {/* ... rest of your form fields ... */}
        
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Video Title
          </label>
          <input 
            type="text" 
            value={title}
            onChange={(e) => setTitle(e.target.value)}
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
        
        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Video Recording Date *
          </label>
          <input 
            type="date" 
            value={videoDate}
            onChange={(e) => setVideoDate(e.target.value)}
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

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
              Start Time
            </label>
            <input 
              type="time" 
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
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
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
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
        
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Location *
          </label>
          <select 
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
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
                  Video is being processed. You can check the analysis results shortly.
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
            disabled={!selectedFile || uploading || isProcessing}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderRadius: '4px',
              backgroundColor: (uploading || isProcessing) ? '#9ca3af' : '#3b82f6',
              color: 'white',
              cursor: (!selectedFile || uploading || isProcessing) ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              opacity: (!selectedFile || uploading || isProcessing) ? 0.6 : 1
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