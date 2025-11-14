//src/contexts/ProgressContext.js
import React, { createContext, useContext, useReducer, useEffect } from 'react';
import axios from 'axios';

const ProgressContext = createContext();

const progressReducer = (state, action) => {
  switch (action.type) {
    case 'ADD_VIDEO':
      return {
        ...state,
        videos: {
          ...state.videos,
          [action.videoId]: {
            progress: 0,
            message: 'Initializing...',
            status: 'pending',
            timestamp: Date.now()
          }
        }
      };
    case 'UPDATE_PROGRESS':
      return {
        ...state,
        videos: {
          ...state.videos,
          [action.videoId]: {
            progress: action.progress,
            message: action.message,
            status: action.status,
            timestamp: Date.now()
          }
        }
      };
    case 'REMOVE_VIDEO':
      const newState = { ...state };
      delete newState.videos[action.videoId];
      return newState;
    case 'CLEAR_ALL':
      return { videos: {} };
    default:
      return state;
  }
};

export const ProgressProvider = ({ children }) => {
  const [state, dispatch] = useReducer(progressReducer, { videos: {} });

  // Poll for all active videos
  useEffect(() => {
    const pollAllProgress = () => {
      Object.keys(state.videos).forEach(videoId => {
        const video = state.videos[videoId];
        if (video.status !== 'completed' && video.status !== 'failed') {
          axios.get(`http://127.0.0.1:8000/api/progress/${videoId}/`)
            .then(response => {
              const data = response.data;
              if (data.progress >= 100 || data.status === 'completed') {
                dispatch({
                  type: 'UPDATE_PROGRESS',
                  videoId,
                  progress: 100,
                  message: 'Processing completed!',
                  status: 'completed'
                });
              } else if (data.status === 'failed') {
                dispatch({
                  type: 'UPDATE_PROGRESS',
                  videoId,
                  progress: 0,
                  message: 'Processing failed',
                  status: 'failed'
                });
              } else {
                dispatch({
                  type: 'UPDATE_PROGRESS',
                  videoId,
                  progress: data.progress,
                  message: data.message || `Processing: ${data.progress}%`,
                  status: data.status || 'processing'
                });
              }
            })
            .catch(error => {
              console.error('Error polling progress for video:', videoId, error);
            });
        }
      });
    };

    const interval = setInterval(pollAllProgress, 2000); // Poll every 2 seconds
    return () => clearInterval(interval);
  }, [state.videos]);

  const addVideo = (videoId) => {
    dispatch({ type: 'ADD_VIDEO', videoId });
  };

  const removeVideo = (videoId) => {
    dispatch({ type: 'REMOVE_VIDEO', videoId });
  };

  const clearAll = () => {
    dispatch({ type: 'CLEAR_ALL' });
  };

  return (
    <ProgressContext.Provider value={{
      progress: state.videos,
      addVideo,
      removeVideo,
      clearAll
    }}>
      {children}
    </ProgressContext.Provider>
  );
};

export const useProgress = () => {
  const context = useContext(ProgressContext);
  if (!context) {
    throw new Error('useProgress must be used within a ProgressProvider');
  }
  return context;
};