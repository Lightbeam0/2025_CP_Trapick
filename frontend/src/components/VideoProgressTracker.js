//src/components/VideoProgressTracker.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = process.env.NODE_ENV === 'development' 
  ? 'http://127.0.0.1:8000' 
  : '';

const VideoProgressTracker = ({ videoId, onCompletion }) => {
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState('processing');
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    let ws = null;
    let pollInterval = null;

    // Try WebSocket first
    const protocol = process.env.NODE_ENV === 'development' ? 'ws' : 'wss';
    const wsUrl = `${protocol}://${API_BASE_URL.replace('http://', '').replace('https://', '')}/ws/video-progress/${videoId}/`;
    
    try {
      ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log('Progress WebSocket connected');
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'progress_update') {
          setProgress(data.progress);
          setMessage(data.message || `Processing: ${data.progress}%`);
          setStatus('processing');
        } else if (data.type === 'processing_complete') {
          setProgress(100);
          setMessage('Processing completed!');
          setStatus('completed');
          if (onCompletion) onCompletion(videoId);
        }
      };

      ws.onclose = () => {
        console.log('Progress WebSocket disconnected');
        setWsConnected(false);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
      };
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      setWsConnected(false);
    }

    // Fallback to HTTP polling if WebSocket fails
    if (!wsConnected) {
      pollInterval = setInterval(async () => {
        try {
          const response = await axios.get(`${API_BASE_URL}/api/progress/${videoId}/`);
          const progressData = response.data;
          
          setProgress(progressData.progress || 0);
          setMessage(progressData.message || `Processing: ${progressData.progress}%`);
          setStatus(progressData.status || 'processing');

          if (progressData.progress >= 100 || progressData.status === 'completed') {
            clearInterval(pollInterval);
            setStatus('completed');
            if (onCompletion) onCompletion(videoId);
          }
        } catch (error) {
          console.error('Error polling progress:', error);
        }
      }, 2000); // Poll every 2 seconds
    }

    return () => {
      if (ws) ws.close();
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [videoId, onCompletion, wsConnected]);

  if (progress === 0 && message === '') return null;

  return (
    <div style={{
      width: '100%',
      height: '6px',
      backgroundColor: '#e5e7eb',
      borderRadius: '3px',
      overflow: 'hidden',
      marginTop: '8px'
    }}>
      <div style={{
        width: `${progress}%`,
        height: '100%',
        backgroundColor: progress === 100 ? '#10b981' : '#3b82f6',
        transition: 'width 0.3s ease',
        borderRadius: '3px'
      }}></div>
      <div style={{
        fontSize: '12px',
        color: '#6b7280',
        marginTop: '4px',
        textAlign: 'center'
      }}>
        {message}
      </div>
    </div>
  );
};

export default VideoProgressTracker;