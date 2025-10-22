// src/utils/uploadHelpers.js

// Smart metadata extraction
export const extractMetadataFromFilename = (filename) => {
  const nameWithoutExt = filename.replace(/\.[^/.]+$/, "");
  
  // Common traffic camera filename patterns
  const patterns = [
    // Pattern: LOCATION_YYYYMMDD_HHMMSS.mp4
    /^([A-Za-z]+)_(\d{8})_(\d{6})/,
    // Pattern: CAMERAID_YYYY-MM-DD_HH-MM-SS.mp4
    /^([A-Za-z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})/,
    // Pattern: DD-MM-YYYY_HHMM_Location.mp4
    /^(\d{2}-\d{2}-\d{4})_(\d{4})_([A-Za-z]+)/
  ];

  for (const pattern of patterns) {
    const match = filename.match(pattern);
    if (match) {
      return {
        filename: nameWithoutExt,
        title: nameWithoutExt,
        video_date: parseDateFromMatch(match),
        start_time: parseTimeFromMatch(match)
      };
    }
  }

  // Fallback: use filename as title
  return {
    filename: nameWithoutExt,
    title: nameWithoutExt
  };
};

// Quick upload presets
export const uploadPresets = {
  quick: {
    autoFillMetadata: true,
    useWebSocket: true,
    showAdvanced: false
  },
  detailed: {
    autoFillMetadata: true,
    useWebSocket: true,
    showAdvanced: true
  },
  batch: {
    autoFillMetadata: true,
    useWebSocket: false, // Use polling for multiple files
    showAdvanced: false
  }
};