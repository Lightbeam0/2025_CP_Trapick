import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import API_CONFIG from '../config/api';

const VideoProgressTracker = ({ videoId, onCompletion, onFailure }) => {
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState('processing');

  // Use refs for cleanup — avoids stale closure issues
  const wsRef = useRef(null);
  const pollRef = useRef(null);
  const isCompletedRef = useRef(false);

  useEffect(() => {
    if (!videoId) return;
    isCompletedRef.current = false;

    const finish = (succeeded, vid) => {
      if (isCompletedRef.current) return;
      isCompletedRef.current = true;

      clearInterval(pollRef.current);
      if (wsRef.current) wsRef.current.close(1000, 'Done');

      if (succeeded) {
        setProgress(100);
        setMessage('Processing completed!');
        setStatus('completed');
        onCompletion?.(vid);
      } else {
        setMessage('Processing failed.');
        setStatus('failed');
        onFailure?.(vid);
      }
    };

    const startPolling = () => {
      if (pollRef.current) return; // Already polling
      pollRef.current = setInterval(async () => {
        if (isCompletedRef.current) {
          clearInterval(pollRef.current);
          return;
        }
        try {
          const { data } = await axios.get(
            `${API_CONFIG.BASE_URL}/api/progress/${videoId}/`,
            { withCredentials: true }
          );
          setProgress(data.progress ?? 0);
          setMessage(data.message || `Processing: ${data.progress ?? 0}%`);
          setStatus(data.status || 'processing');

          if (data.status === 'completed' || data.progress >= 100) {
            finish(true, videoId);
          } else if (data.status === 'failed') {
            finish(false, videoId);
          }
        } catch (err) {
          console.error('Progress poll error:', err);
        }
      }, 2000);
    };

    // ── WebSocket (primary) ──────────────────────────────────────────────
    // Use the centrally-configured WS URL so dev/prod are consistent.
    const wsUrl = `${API_CONFIG.WS_URL}/video-progress/${videoId}/`;
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
    } catch (err) {
      console.error('WebSocket construction failed:', err);
      startPolling();
      return;
    }

    // If WS doesn't open within 3 s, fall back to polling
    const wsTimeout = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        console.warn('WebSocket did not open in time — falling back to polling');
        ws.close();
        startPolling();
      }
    }, 3000);

    ws.onopen = () => {
      clearTimeout(wsTimeout);
      console.log(`[VideoProgressTracker] WS connected for ${videoId}`);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'progress_update') {
          setProgress(data.progress ?? 0);
          setMessage(data.message || `Processing: ${data.progress ?? 0}%`);
          setStatus('processing');

        } else if (data.type === 'processing_complete') {
          finish(true, videoId);

        } else if (data.type === 'processing_failed') {
          // ← was missing; backend sends this on task failure
          setMessage(data.message || 'Processing failed.');
          finish(false, videoId);
        }
      } catch (err) {
        console.error('WS message parse error:', err);
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket error — switching to polling:', err);
      clearTimeout(wsTimeout);
      startPolling();
    };

    ws.onclose = (event) => {
      clearTimeout(wsTimeout);
      // If closed unexpectedly before completion, fall back to polling
      if (!isCompletedRef.current && event.code !== 1000) {
        console.warn('WebSocket closed unexpectedly — switching to polling');
        startPolling();
      }
    };

    return () => {
      clearTimeout(wsTimeout);
      clearInterval(pollRef.current);
      pollRef.current = null;
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
        wsRef.current = null;
      }
    };
  }, [videoId]); // ← only re-run when videoId changes; callbacks via refs

  // Keep callback refs fresh without triggering the effect
  const onCompletionRef = useRef(onCompletion);
  const onFailureRef = useRef(onFailure);
  useEffect(() => { onCompletionRef.current = onCompletion; }, [onCompletion]);
  useEffect(() => { onFailureRef.current = onFailure; }, [onFailure]);

  if (progress === 0 && message === '') return null;

  const isFailed = status === 'failed';
  const barColor = isFailed ? '#ef4444' : progress === 100 ? '#10b981' : '#3b82f6';

  return (
    <div style={{ width: '100%', marginTop: '8px' }}>
      <div style={{
        width: '100%',
        height: '6px',
        backgroundColor: '#e5e7eb',
        borderRadius: '3px',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${isFailed ? 100 : progress}%`,
          height: '100%',
          backgroundColor: barColor,
          transition: 'width 0.3s ease',
          borderRadius: '3px',
        }} />
      </div>
      {message && (
        <div style={{
          fontSize: '12px',
          color: isFailed ? '#ef4444' : '#6b7280',
          marginTop: '4px',
          textAlign: 'center',
        }}>
          {message}
        </div>
      )}
    </div>
  );
};

export default VideoProgressTracker;