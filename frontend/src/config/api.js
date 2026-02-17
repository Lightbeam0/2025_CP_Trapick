// src/config/api.js - COMPLETE FIXED VERSION
const getApiBaseUrl = () => {
  if (process.env.NODE_ENV === 'development') {
    return 'http://127.0.0.1:8000';
  } else {
    // Production: use relative path (same origin as frontend)
    return '';
  }
};

const API_CONFIG = {
  BASE_URL: getApiBaseUrl(),
  WS_URL: process.env.NODE_ENV === 'development' 
    ? 'ws://127.0.0.1:8000/ws'
    : `wss://${window.location.host}/ws`,
  TIMEOUT: 30000,
};

export const ENDPOINTS = {
  // Video endpoints
  UPLOAD_VIDEO: `${API_CONFIG.BASE_URL}/api/upload/video/`,
  VIDEO_PROGRESS: (videoId) => `${API_CONFIG.BASE_URL}/api/progress/${videoId}/`,
  ANALYSIS_RESULTS: (uploadId) => `${API_CONFIG.BASE_URL}/api/analysis/${uploadId}/`,
  VIDEO_LIST: `${API_CONFIG.BASE_URL}/api/videos/`,
  DELETE_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/api/videos/${videoId}/`,
  
  // Video viewing
  VIEW_PROCESSED_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/api/video/${videoId}/view/`,
  DOWNLOAD_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/api/video/${videoId}/download/`,
  DIRECT_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/api/video/${videoId}/direct/`,
  
  // Data endpoints
  ANALYSIS_OVERVIEW: `${API_CONFIG.BASE_URL}/api/analyze/`,
  VEHICLE_STATS: `${API_CONFIG.BASE_URL}/api/vehicles/`,
  CONGESTION_DATA: `${API_CONFIG.BASE_URL}/api/congestion/`,
  LOCATIONS: `${API_CONFIG.BASE_URL}/api/locations/`,
  LOCATION_GROUPS: (locationId) => `${API_CONFIG.BASE_URL}/api/locations/${locationId}/groups/`,
  
  // Processing profiles
  PROCESSING_PROFILES: `${API_CONFIG.BASE_URL}/api/processing-profiles/`,
  
  // Auth
  LOGIN: `${API_CONFIG.BASE_URL}/api/auth/login/`,
};

// Export as default
export default API_CONFIG;