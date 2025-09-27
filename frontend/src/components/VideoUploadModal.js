// src/components/VideoUploadModal.js
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

  // Poll for progress when processing
  useEffect(() => {
    let intervalId;
    
    if (isProcessing && uploadId) {
      intervalId = setInterval(async () => {
        try {
          const response = await axios.get(`http://127.0.0.1:8000/api/progress/${uploadId}/`);
          const progressData = response.data;
          
          setCurrentProgress(progressData.progress || 0);
          setProgressMessage(progressData.message || '');
          
          // If progress is 100%, processing is complete
          if (progressData.progress === 100) {
            setIsProcessing(false);
            setUploading(false);
            setProgressMessage('Processing completed!');
            
            // Notify parent component
            if (onUpload) {
              onUpload({ upload_id: uploadId, status: 'completed' });
            }
            
            // Clear progress after 5 seconds
            setTimeout(() => {
              setCurrentProgress(0);
              setProgressMessage('');
            }, 5000);
          }
        } catch (error) {
          console.error('Error fetching progress:', error);
        }
      }, 2000); // Poll every 2 seconds
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isProcessing, uploadId, onUpload]);

  // Add WebSocket effect
  useEffect(() => {
    if (isProcessing && uploadId) {
      // Connect to WebSocket for real-time updates
      const ws = new WebSocket(`ws://127.0.0.1:8000/ws/progress/${uploadId}/`);
      
      ws.onopen = () => {
        console.log('WebSocket connected for progress updates');
        setWebsocketConnected(true);
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setCurrentProgress(data.progress || 0);
        setProgressMessage(data.message || '');
        
        // If progress is 100%, processing is complete
        if (data.progress === 100) {
          setIsProcessing(false);
          setUploading(false);
          setProgressMessage('Processing completed!');
          
          // Notify parent component
          if (onUpload) {
            onUpload({ upload_id: uploadId, status: 'completed' });
          }
          
          // Clear progress after 5 seconds
          setTimeout(() => {
            setCurrentProgress(0);
            setProgressMessage('');
          }, 5000);
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWebsocketConnected(false);
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWebsocketConnected(false);
      };
      
      setWebsocketConnected(true);
    }
    
    return () => {
      // Disconnect WebSocket
      if (websocketConnected) {
        setWebsocketConnected(false);
      }
    };
  }, [isProcessing, uploadId, onUpload]);

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Validate file type
      const validTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/webm', 'video/quicktime'];
      if (!validTypes.includes(file.type)) {
        alert('Please select a valid video file (MP4, AVI, MOV, WebM)');
        return;
      }
      
      // Validate file size (500MB max)
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
    if (!selectedFile) {
      alert('Please select a video file first!');
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
    if (locationId) {
      formData.append('location_id', locationId);
    }

    try {
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
          }
        }
      });
      
      setUploadId(response.data.upload_id);
      setUploadResult({ success: true, data: response.data });
      setProgressMessage('Upload complete! Starting video analysis...');
      
    } catch (error) {
      console.error('Upload error:', error);
      const errorMessage = error.response?.data?.error || error.message || 'Upload failed';
      setUploadResult({ success: false, error: errorMessage });
      setUploading(false);
      setIsProcessing(false);
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
        
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
            Location (Optional)
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
            disabled={uploading || isProcessing}
          >
            <option value="">Select a location</option>
            <option value="1">Baliwasan Area</option>
            <option value="2">San Roque</option>
            <option value="3">Downtown Zamboanga</option>
            <option value="4">Tetuan</option>
            <option value="5">Guiwan</option>
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
                {uploadResult.data.upload_id && (
                  <p style={{ margin: '4px 0 0 0', fontSize: '12px', fontFamily: 'monospace' }}>
                    ID: {uploadResult.data.upload_id}
                  </p>
                )}
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

        <div style={{ marginTop: '16px', fontSize: '12px', color: '#6b7280' }}>
          <p><strong>Supported formats:</strong> MP4, AVI, MOV, WebM</p>
          <p><strong>Max file size:</strong> 500MB</p>
          <p><strong>Processing time:</strong> Depends on video length and complexity</p>
          <p><strong>Real-time progress:</strong> Track upload and analysis progress</p>
        </div>
      </div>
    </div>
  );
};

export default VideoUploadModal;