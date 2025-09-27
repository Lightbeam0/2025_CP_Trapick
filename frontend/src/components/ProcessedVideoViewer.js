// src/components/ProcessedVideoViewer.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ProcessedVideoViewer = ({ videoId, onClose, onBack }) => {
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [videoInfo, setVideoInfo] = useState(null);
  const [videoLoadError, setVideoLoadError] = useState(null);

  useEffect(() => {
    const fetchVideoData = async () => {
      try {
        setLoading(true);
        setError(null);
        setVideoLoadError(null);
        
        console.log(`Fetching data for video ID: ${videoId}`);
        
        // Get analysis data
        const analysisResponse = await axios.get(`http://127.0.0.1:8000/api/analysis/${videoId}/`);
        console.log("Analysis data loaded:", analysisResponse.data);
        
        setAnalysisData(analysisResponse.data.analysis);
        setVideoInfo(analysisResponse.data.video_info);
        
        // Use direct video URL for viewing (NOT download endpoint)
        const directVideoUrl = `http://127.0.0.1:8000/api/video/${videoId}/view/`;
        console.log("Setting video URL to:", directVideoUrl);
        
        // Test if the video endpoint is accessible
        try {
          const testResponse = await axios.head(directVideoUrl, { timeout: 10000 });
          console.log("Video endpoint test successful:", testResponse.status);
        } catch (testError) {
          console.warn('Video endpoint test failed, but will try to play anyway:', testError.message);
        }
        
        setVideoUrl(directVideoUrl);
        
      } catch (err) {
        console.error('Error loading video data:', err);
        if (err.response?.status === 404) {
          setError('Analysis data not found. The video may not exist or is still processing.');
        } else if (err.code === 'NETWORK_ERROR' || err.message.includes('Network Error')) {
          setError('Network error. Please check if the Django server is running.');
        } else {
          setError('Error loading analysis data: ' + (err.response?.data?.error || err.message));
        }
      } finally {
        setLoading(false);
      }
    };

    if (videoId) {
      fetchVideoData();
    }

    // Cleanup function
    return () => {
      // Note: We're not using blob URLs anymore, so no need to revoke
    };
  }, [videoId]);

  const handleVideoError = (e) => {
    console.error('Video playback error:', e);
    setVideoLoadError('Error playing video. The video file may be corrupted, still processing, or the format is not supported.');
    
    // Provide alternative download option
    const downloadUrl = `http://127.0.0.1:8000/api/video/${videoId}/download/`;
    console.log('Alternative download URL:', downloadUrl);
  };

  const handleDownloadVideo = () => {
    const downloadUrl = `http://127.0.0.1:8000/api/video/${videoId}/download/`;
    window.open(downloadUrl, '_blank');
  };

  const handleTryAlternativeView = () => {
    // Try the direct endpoint as fallback
    const alternativeUrl = `http://127.0.0.1:8000/api/video/${videoId}/direct/`;
    setVideoUrl(alternativeUrl);
    setVideoLoadError(null);
    console.log('Trying alternative video URL:', alternativeUrl);
  };

  // Export functions
  const handleExportCSV = () => {
    const exportUrl = `http://127.0.0.1:8000/api/export/${videoId}/csv/`;
    window.open(exportUrl, '_blank');
  };

  const handleExportPDF = () => {
    const exportUrl = `http://127.0.0.1:8000/api/export/${videoId}/pdf/`;
    window.open(exportUrl, '_blank');
  };

  const handleExportExcel = () => {
    const exportUrl = `http://127.0.0.1:8000/api/export/${videoId}/excel/`;
    window.open(exportUrl, '_blank');
  };

  // Simple loading component
  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading analysis data...</div>
            <div style={{ 
              width: '40px', 
              height: '40px', 
              border: '4px solid #f3f3f3', 
              borderTop: '4px solid #3b82f6', 
              borderRadius: '50%', 
              margin: '0 auto', 
              animation: 'spin 1s linear infinite' 
            }}></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="main-content">
        <div style={{ padding: '40px', textAlign: 'center' }}>
          <div style={{ color: '#ef4444', fontSize: '18px', marginBottom: '16px' }}>{error}</div>
          <button 
            onClick={onClose}
            style={{
              padding: '10px 20px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              backgroundColor: 'white',
              cursor: 'pointer',
              margin: '5px'
            }}
          >
            Back to Analysis List
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 4px 0' }}>
            Processed Video Analysis
          </h1>
          {videoInfo && (
            <p style={{ color: '#666', margin: 0 }}>
              {videoInfo.filename} • Uploaded: {new Date(videoInfo.uploaded_at).toLocaleDateString()}
            </p>
          )}
        </div>
        <button 
          onClick={onClose}
          style={{
            padding: '10px 20px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            backgroundColor: 'white',
            cursor: 'pointer',
            fontWeight: '500'
          }}
        >
          Back to List
        </button>
      </div>

      {/* Analysis Summary */}
      {analysisData && (
        <div className="dashboard-card" style={{ marginBottom: '24px' }}>
          <h3 style={{ marginBottom: '16px' }}>Analysis Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
                {analysisData.total_vehicles || 0}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Total Vehicles</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
                {analysisData.processing_time ? analysisData.processing_time.toFixed(1) : 0}s
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Processing Time</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysisData.congestion_level === 'high' ? '#ef4444' : '#f59e0b' }}>
                {analysisData.congestion_level || 'Unknown'}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Congestion Level</div>
            </div>
            
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#8b5cf6' }}>
                {analysisData.traffic_pattern || 'Unknown'}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Traffic Pattern</div>
            </div>
          </div>

          {/* Vehicle Breakdown */}
          {analysisData.vehicle_breakdown && (
            <div>
              <h4 style={{ marginBottom: '12px' }}>Vehicle Breakdown</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
                {Object.entries(analysisData.vehicle_breakdown).map(([vehicleType, count]) => (
                  <div key={vehicleType} style={{
                    padding: '12px',
                    backgroundColor: '#f8fafc',
                    borderRadius: '6px',
                    textAlign: 'center'
                  }}>
                    <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#2d3748' }}>
                      {count}
                    </div>
                    <div style={{ fontSize: '12px', color: '#666', textTransform: 'capitalize' }}>
                      {vehicleType}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Export Buttons */}
      <div style={{ marginTop: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
        <button onClick={handleExportPDF} style={{ padding: '8px 16px', border: '1px solid #dc2626', borderRadius: '4px', backgroundColor: 'white', color: '#dc2626', cursor: 'pointer' }}>
          Export PDF
        </button>
        <button onClick={handleExportCSV} style={{ padding: '8px 16px', border: '1px solid #059669', borderRadius: '4px', backgroundColor: 'white', color: '#059669', cursor: 'pointer' }}>
          Export CSV
        </button>
        <button onClick={handleExportExcel} style={{ padding: '8px 16px', border: '1px solid #3b82f6', borderRadius: '4px', backgroundColor: 'white', color: '#3b82f6', cursor: 'pointer' }}>
          Export Excel
        </button>
      </div>

      {/* Processed Video Section */}
      <div className="dashboard-card">
        <h3 style={{ marginBottom: '16px' }}>Processed Video with Detection Overlay</h3>
        
        {videoLoadError && (
          <div style={{ 
            marginBottom: '20px', 
            padding: '16px', 
            backgroundColor: '#fee2e2', 
            border: '1px solid #fecaca',
            borderRadius: '8px',
            color: '#dc2626'
          }}>
            <strong>Video Playback Error:</strong> {videoLoadError}
            <div style={{ marginTop: '10px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              <button 
                onClick={handleTryAlternativeView}
                style={{
                  padding: '8px 16px',
                  border: '1px solid #dc2626',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  color: '#dc2626',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Try Alternative View
              </button>
              <button 
                onClick={handleDownloadVideo}
                style={{
                  padding: '8px 16px',
                  border: '1px solid #3b82f6',
                  borderRadius: '4px',
                  backgroundColor: '#3b82f6',
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Download Video Instead
              </button>
            </div>
          </div>
        )}

        {videoUrl ? (
          <div>
            <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: '#f0f9ff', borderRadius: '6px' }}>
              <p style={{ margin: 0, fontSize: '14px', color: '#3b82f6' }}>
                <strong>Video URL:</strong> <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>{videoUrl}</span>
              </p>
            </div>
            
            <video 
              controls 
              style={{ 
                width: '100%', 
                maxHeight: '70vh', 
                border: '2px solid #e5e7eb', 
                borderRadius: '8px',
                backgroundColor: '#000'
              }}
              onError={handleVideoError}
              onLoadStart={() => console.log('Video loading started')}
              onCanPlay={() => console.log('Video can play')}
              onWaiting={() => console.log('Video waiting')}
              onPlaying={() => console.log('Video playing')}
            >
              <source src={videoUrl} type="video/mp4" />
              <source src={videoUrl} type="video/mp4; codecs=avc1.42E01E,mp4a.40.2" />
              Your browser does not support the video tag.
            </video>
            
            <div style={{ marginTop: '20px', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
              <h4 style={{ marginBottom: '12px' }}>Video Controls & Troubleshooting</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px', fontSize: '14px' }}>
                <div>
                  <strong>If video doesn't play:</strong>
                  <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
                    <li>Try downloading the video using the button below</li>
                    <li>Check browser console (F12) for errors</li>
                    <li>Try refreshing the page</li>
                    <li>Try a different web browser</li>
                  </ul>
                </div>
                <div>
                  <strong>Quick Actions:</strong>
                  <div style={{ marginTop: '8px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    <button 
                      onClick={handleDownloadVideo}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid #10b981',
                        borderRadius: '4px',
                        backgroundColor: '#10b981',
                        color: 'white',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      Download Video
                    </button>
                    <button 
                      onClick={() => window.open(videoUrl, '_blank')}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid #3b82f6',
                        borderRadius: '4px',
                        backgroundColor: 'white',
                        color: '#3b82f6',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      Open in New Tab
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
            <div style={{ fontSize: '16px', color: '#666', marginBottom: '16px' }}>
              Processed video not available
            </div>
            <p style={{ color: '#999', fontSize: '14px', marginBottom: '20px' }}>
              The processed video with detection overlays is not available for this analysis.
              This could be because the video is still processing or there was an issue during processing.
            </p>
            <button 
              onClick={handleDownloadVideo}
              style={{
                padding: '10px 20px',
                border: '1px solid #3b82f6',
                borderRadius: '4px',
                backgroundColor: '#3b82f6',
                color: 'white',
                cursor: 'pointer'
              }}
            >
              Check for Video Download
            </button>
          </div>
        )}
      </div>

      {/* Detection Legend */}
      <div className="dashboard-card" style={{ marginTop: '24px' }}>
        <h4 style={{ marginBottom: '12px' }}>Detection Legend</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px', fontSize: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '16px', height: '16px', backgroundColor: '#00ff00', borderRadius: '2px' }}></div>
            <span>Car</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '16px', height: '16px', backgroundColor: '#ffa500', borderRadius: '2px' }}></div>
            <span>Truck</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '16px', height: '16px', backgroundColor: '#ff0000', borderRadius: '2px' }}></div>
            <span>Bus</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '16px', height: '16px', backgroundColor: '#ffff00', borderRadius: '2px' }}></div>
            <span>Motorcycle</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '16px', height: '16px', backgroundColor: '#ff00ff', borderRadius: '2px' }}></div>
            <span>Bicycle</span>
          </div>
        </div>
        <div style={{ marginTop: '12px', fontSize: '12px', color: '#666' }}>
          <p><strong>Yellow rectangle:</strong> Counting zone • <strong>Colored trails:</strong> Vehicle tracking paths</p>
          <p><strong>White text overlay:</strong> Real-time statistics and frame information</p>
        </div>
      </div>

      {/* Accuracy Assessment Guide */}
      <div className="dashboard-card" style={{ marginTop: '24px' }}>
        <h3 style={{ marginBottom: '16px' }}>Accuracy Assessment Guide</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          <div>
            <h4 style={{ marginBottom: '8px', fontSize: '14px' }}>What to Look For:</h4>
            <ul style={{ fontSize: '14px', lineHeight: '1.5', color: '#666' }}>
              <li><strong>Bounding box accuracy:</strong> Are vehicles properly outlined?</li>
              <li><strong>Counting zone:</strong> Are vehicles counted when they enter the yellow zone?</li>
              <li><strong>Vehicle classification:</strong> Are vehicles correctly identified?</li>
              <li><strong>Tracking consistency:</strong> Do vehicles maintain the same ID?</li>
            </ul>
          </div>
          <div>
            <h4 style={{ marginBottom: '8px', fontSize: '14px' }}>Quality Indicators:</h4>
            <ul style={{ fontSize: '14px', lineHeight: '1.5', color: '#666' }}>
              <li><strong>High confidence scores</strong> (&gt;0.7 is good)</li>
              <li><strong>Consistent tracking</strong> throughout the video</li>
              <li><strong>Accurate vehicle counts</strong> matching visual inspection</li>
              <li><strong>Proper congestion level</strong> assessment</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProcessedVideoViewer;