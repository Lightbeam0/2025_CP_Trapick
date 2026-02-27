// src/contexts/WebSocketContext.js
import React, { createContext, useContext, useReducer, useCallback, useEffect } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

// Create context
const WebSocketContext = createContext();

// Progress reducer for state management
const progressReducer = (state, action) => {
  switch (action.type) {
    case 'UPDATE_PROGRESS': {
      const existing = state[action.payload.videoId] || {};

      // ✅ FIX: Never overwrite a completed or failed status with processing
      if (
        (existing.status === 'completed' || existing.status === 'failed') &&
        action.payload.data.status === 'processing'
      ) {
        return state; // ignore late progress_update messages after completion
      }

      return {
        ...state,
        [action.payload.videoId]: {
          ...existing,
          ...action.payload.data,
          video_id: action.payload.videoId,
          lastUpdated: new Date().toISOString(),
        },
      };
    }

    case 'REMOVE_PROGRESS': {
      const newState = { ...state };
      delete newState[action.payload.videoId];
      return newState;
    }

    case 'SET_ALL_PROGRESS':
      return action.payload.progressData;

    case 'CLEAR_ALL_PROGRESS':
      return {};

    default:
      return state;
  }
};

// WebSocket Provider Component
export const WebSocketProvider = ({ children }) => {
  const [progressData, dispatch] = useReducer(progressReducer, {});

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback((data) => {
    console.log('📨 WebSocket Context processing message:', data);

    try {
      const messageData = typeof data === 'string' ? JSON.parse(data) : data;

      switch (messageData.type) {
        case 'progress_update':
          console.log('📊 Progress update received:', messageData);
          dispatch({
            type: 'UPDATE_PROGRESS',
            payload: {
              videoId: messageData.video_id,
              data: {
                progress: messageData.progress,
                message: messageData.message,
                // ✅ FIX: use status from message if present, else default to 'processing'
                status: messageData.status || 'processing',
              },
            },
          });
          break;

        case 'processing_complete':
          console.log('🎉 Processing complete received:', messageData);
          dispatch({
            type: 'UPDATE_PROGRESS',
            payload: {
              videoId: messageData.video_id,
              data: {
                progress: 100,
                status: 'completed',
                // ✅ FIX: video_info is at root of messageData (not nested)
                video_info: messageData.video_info || null,
                message: messageData.message || 'Processing completed!',
                completed_at: new Date().toISOString(),
              },
            },
          });
          break;

        case 'processing_failed':
          console.log('❌ Processing failed received:', messageData);
          dispatch({
            type: 'UPDATE_PROGRESS',
            payload: {
              videoId: messageData.video_id,
              data: {
                progress: 0,
                status: 'failed',
                message: messageData.message,
                error: messageData.error_details,
                failed_at: new Date().toISOString(),
              },
            },
          });
          break;

        case 'connection_established':
          console.log('✅ WebSocket connection established');
          break;

        default:
          console.warn('⚠️ Unknown WebSocket message type:', messageData.type);
      }
    } catch (error) {
      console.error('❌ Error processing WebSocket message:', error);
    }
  }, []);

  // Initialize WebSocket connection
  const {
    connectionStatus,
    isConnected,
    sendMessage,
    connect,
    disconnect,
  } = useWebSocket({
    onMessage: handleWebSocketMessage,
    onStatusChange: (status) => {
      console.log(`🔌 WebSocket status changed: ${status}`);
    },
  });

  // Context methods
  const updateVideoProgress = useCallback((videoId, data) => {
    console.log('📝 Manually updating progress:', videoId, data);
    dispatch({ type: 'UPDATE_PROGRESS', payload: { videoId, data } });
  }, []);

  const removeVideoProgress = useCallback((videoId) => {
    dispatch({ type: 'REMOVE_PROGRESS', payload: { videoId } });
  }, []);

  const clearAllProgress = useCallback(() => {
    dispatch({ type: 'CLEAR_ALL_PROGRESS' });
  }, []);

  const getVideoProgress = useCallback(
    (videoId) => progressData[videoId] || null,
    [progressData]
  );

  const getAllProgress = useCallback(() => progressData, [progressData]);

  // Calculate statistics
  const getProgressStats = useCallback(() => {
    const videoIds = Object.keys(progressData);

    const stats = videoIds.reduce(
      (acc, videoId) => {
        const video = progressData[videoId];
        if (video.status === 'processing') acc.active++;
        else if (video.status === 'completed') acc.completed++;
        else if (video.status === 'failed') acc.failed++;
        return acc;
      },
      { active: 0, completed: 0, failed: 0 }
    );

    return {
      total: videoIds.length,
      active: stats.active,
      completed: stats.completed,
      failed: stats.failed,
      videoIds,
      details: progressData,
    };
  }, [progressData]);

  const contextValue = {
    // Connection state
    connectionStatus,
    isConnected,

    // Connection management
    connectWebSocket: connect,
    disconnectWebSocket: disconnect,
    sendWebSocketMessage: sendMessage,

    // Progress data
    progressData: getAllProgress(),
    progressStats: getProgressStats(),

    // Progress management
    getVideoProgress,
    updateVideoProgress,
    removeVideoProgress,
    clearAllProgress,

    // Helper
    hasActiveVideos: getProgressStats().active > 0,
  };

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

// Custom hook to use the WebSocket context
export const useWebSocketContext = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
};