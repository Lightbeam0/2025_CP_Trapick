// src/hooks/useVideoProgress.js
import { useWebSocketContext } from '../contexts/WebSocketContext';

/**
 * Hook to access video progress functionality
 * Can be used with or without a specific videoId
 */
export const useVideoProgress = (videoId = null) => {
  const context = useWebSocketContext();
  
  const { 
    progressData, 
    progressStats,
    getVideoProgress, 
    updateVideoProgress, 
    removeVideoProgress,
    connectionStatus,
    isConnected
  } = context;

  // Get specific video progress if videoId provided
  const progress = videoId ? getVideoProgress(videoId) : null;

  // Helper methods for specific video
  const updateProgress = (progressUpdate) => {
    if (videoId) {
      updateVideoProgress(videoId, progressUpdate);
    }
  };

  const removeProgress = () => {
    if (videoId) {
      removeVideoProgress(videoId);
    }
  };

  // Check if specific video is completed
  const isCompleted = progress?.status === 'completed';
  const isFailed = progress?.status === 'failed';
  const isProcessing = progress?.status === 'processing';

  return {
    // Specific video progress (if videoId provided)
    progress,
    updateProgress,
    removeProgress,
    isCompleted,
    isFailed,
    isProcessing,
    
    // All progress data
    allProgress: progressData,
    progressStats,
    
    // Connection info
    connectionStatus,
    isConnected,
    
    // Global progress methods
    getVideoProgress,
    updateVideoProgress,
    removeVideoProgress
  };
};