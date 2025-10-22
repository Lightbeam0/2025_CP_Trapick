// src/services/uploadService.js
import axios from 'axios';
import WebSocketService from './websocketService';

class UploadService {
  constructor() {
    this.uploadQueue = new Map();
    this.isProcessing = false;
  }

  async uploadVideo(formData, options = {}) {
    const {
      onProgress,
      onComplete,
      onError,
      useWebSocket = true
    } = options;

    try {
      // Single API call for upload
      const response = await axios.post('http://127.0.0.1:8000/api/upload/video/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress?.(progress, `Uploading: ${progress}%`);
        }
      });

      const { upload_id, session_id } = response.data;
      
      // Simplified progress tracking - choose ONE method
      if (useWebSocket) {
        this.setupWebSocketProgress(upload_id, onProgress, onComplete);
      } else {
        this.setupPollingProgress(upload_id, onProgress, onComplete);
      }

      return { upload_id, session_id, success: true };

    } catch (error) {
      onError?.(error.response?.data?.error || error.message);
      return { success: false, error: error.message };
    }
  }

  setupWebSocketProgress(uploadId, onProgress, onComplete) {
    WebSocketService.connectToVideoProgress(uploadId, 
      (progress, message) => onProgress?.(progress, message),
      (videoId, message) => onComplete?.({ upload_id: videoId, message })
    );
  }

  setupPollingProgress(uploadId, onProgress, onComplete) {
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`http://127.0.0.1:8000/api/progress/${uploadId}/`);
        const { progress, message } = response.data;
        
        onProgress?.(progress, message);
        
        if (progress === 100) {
          clearInterval(pollInterval);
          onComplete?.({ upload_id: uploadId, message: 'Processing completed!' });
        }
      } catch (error) {
        console.error('Progress polling error:', error);
      }
    }, 2000);
  }
}

export default new UploadService();