  // src/config/api.js
  const API_CONFIG = {
    BASE_URL: 'http://127.0.0.1:8000',  // Remove /api from here
    WS_URL: 'ws://127.0.0.1:8000/ws',
    TIMEOUT: 30000,
  };

  export const ENDPOINTS = {
    // Video endpoints - remove /api from all URLs
    UPLOAD_VIDEO: `${API_CONFIG.BASE_URL}/upload/video/`,
    VIDEO_PROGRESS: (videoId) => `${API_CONFIG.BASE_URL}/progress/${videoId}/`,
    ANALYSIS_RESULTS: (uploadId) => `${API_CONFIG.BASE_URL}/analysis/${uploadId}/`,
    VIDEO_LIST: `${API_CONFIG.BASE_URL}/videos/`,
    DELETE_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/videos/${videoId}/`,
    
    // Video viewing
    VIEW_PROCESSED_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/video/${videoId}/view/`,
    DOWNLOAD_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/video/${videoId}/download/`,
    DIRECT_VIDEO: (videoId) => `${API_CONFIG.BASE_URL}/video/${videoId}/direct/`,
    
    // Data endpoints
    ANALYSIS_OVERVIEW: `${API_CONFIG.BASE_URL}/analyze/`,
    VEHICLE_STATS: `${API_CONFIG.BASE_URL}/vehicles/`,
    CONGESTION_DATA: `${API_CONFIG.BASE_URL}/congestion/`,
    LOCATIONS: `${API_CONFIG.BASE_URL}/locations/`,
    
    // Processing profiles
    PROCESSING_PROFILES: `${API_CONFIG.BASE_URL}/processing-profiles/`,
    
    // Export endpoints
    EXPORT_CSV: (videoId) => `${API_CONFIG.BASE_URL}/export/${videoId}/csv/`,
    EXPORT_PDF: (videoId) => `${API_CONFIG.BASE_URL}/export/${videoId}/pdf/`,
    EXPORT_EXCEL: (videoId) => `${API_CONFIG.BASE_URL}/export/${videoId}/excel/`,
    
    // Prediction endpoints
    GENERATE_PREDICTIONS: `${API_CONFIG.BASE_URL}/predictions/generate/`,
    GET_PREDICTIONS: `${API_CONFIG.BASE_URL}/predictions/`,
    PREDICTION_INSIGHTS: `${API_CONFIG.BASE_URL}/predictions/insights/`,
    PEAK_HOURS: `${API_CONFIG.BASE_URL}/predictions/peak-hours/`,
    
    // System endpoints
    HEALTH_CHECK: `${API_CONFIG.BASE_URL}/health/`,
    DEBUG_DATA: `${API_CONFIG.BASE_URL}/debug/data/`,
  };