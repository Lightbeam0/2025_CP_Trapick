// src/components/ProcessedVideoViewer.js
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const ProcessedVideoViewer = ({ videoId, type, onClose, onBack }) => {
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [itemInfo, setItemInfo] = useState(null);
  const [videoLoadError, setVideoLoadError] = useState(null);
  
  // Video element ref for direct DOM management
  const videoRef = useRef(null);

  useEffect(() => {
    const fetchItemData = async () => {
      try {
        setLoading(true);
        setError(null);
        setVideoLoadError(null);

        console.log(`🔍 Fetching data for ${type} ID: ${videoId}`);

        let analysisResponse, videoUrlEndpoint, itemInfoResponse;

        if (type === 'session') {
          // Handle session viewing
          try {
            const sessionAnalysesResponse = await axios.get(`http://127.0.0.1:8000/api/sessions/${videoId}/traffic-analyses/`);
            const sessionAnalyses = sessionAnalysesResponse.data;
            
            if (sessionAnalyses.length > 0) {
              analysisResponse = { data: sessionAnalyses[0] };
              console.log(`✅ Found ${sessionAnalyses.length} analyses for session, using first one`);
              
              itemInfoResponse = await axios.get(`http://127.0.0.1:8000/api/sessions/${videoId}/`);
              videoUrlEndpoint = `http://127.0.0.1:8000/api/session-video/${videoId}/view/`;
            } else {
              throw new Error("No aggregated analysis found for this session.");
            }
          } catch (aggError) {
            console.error("Error fetching aggregated analysis for session:", aggError);
            
            // Fallback: Try the aggregated-analysis endpoint
            try {
              console.warn("Trying aggregated-analysis endpoint as fallback...");
              analysisResponse = await axios.get(`http://127.0.0.1:8000/api/sessions/${videoId}/aggregated-analysis/`);
              itemInfoResponse = await axios.get(`http://127.0.0.1:8000/api/sessions/${videoId}/`);
              videoUrlEndpoint = `http://127.0.0.1:8000/api/session-video/${videoId}/view/`;
            } catch (fallbackError) {
              console.error("Fallback also failed:", fallbackError);
              throw new Error("No analysis data available for this session.");
            }
          }

        } else { // type === 'video'
          // Existing logic for individual video
          analysisResponse = await axios.get(`http://127.0.0.1:8000/api/analysis/${videoId}/`);
          itemInfoResponse = analysisResponse;
          videoUrlEndpoint = `http://127.0.0.1:8000/api/video/${videoId}/view/`;
        }

        console.log(`${type === 'session' ? "Session" : "Video"} analysis data loaded:`, analysisResponse.data);
        setAnalysisData(analysisResponse.data);
        setItemInfo(itemInfoResponse.data);

        // Test if the video endpoint is accessible
        try {
          const testResponse = await axios.head(videoUrlEndpoint, { timeout: 10000 });
          console.log("Video endpoint test successful:", testResponse.status);
        } catch (testError) {
          console.warn('Video endpoint test failed, but will try to play anyway:', testError.message);
        }

        console.log("Setting video URL to:", videoUrlEndpoint);
        setVideoUrl(videoUrlEndpoint);

      } catch (err) {
        console.error(`Error loading ${type} data:`, err);
        if (err.response?.status === 404) {
          setError(`${type === 'session' ? 'Session analysis' : 'Analysis data'} not found. The ${type} may not exist or is still processing.`);
        } else if (err.code === 'NETWORK_ERROR' || err.message.includes('Network Error')) {
          setError('Network error. Please check if the Django server is running.');
        } else {
          setError(`Error loading ${type} data: ${err.response?.data?.error || err.message}`);
        }
      } finally {
        setLoading(false);
      }
    };

    if (videoId && type) {
      fetchItemData();
    }

    return () => {
      // Cleanup if needed
    };
  }, [videoId, type]);

  // Use effect to manage video source with ref
  useEffect(() => {
    if (videoRef.current && videoUrl) {
      // Only set the source if it's different
      if (videoRef.current.src !== videoUrl) {
        console.log("🔄 Setting video source via ref:", videoUrl);
        videoRef.current.src = videoUrl;
        // Don't call load() here as it can cause unnecessary reloads
      }
    }
  }, [videoUrl]);

  const renderYJunctionAnalysis = (analysisData) => {
    if (!analysisData.path_analysis) return null;

    return (
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <h3 style={{ marginBottom: '16px' }}>Y-Junction Path Analysis</h3>
        
        {/* Busiest Path */}
        {analysisData.path_analysis.busiest_path && (
          <div style={{
            backgroundColor: '#f0f9ff',
            padding: '16px',
            borderRadius: '8px',
            marginBottom: '16px',
            border: '2px solid #3b82f6'
          }}>
            <h4 style={{ margin: '0 0 8px 0', color: '#1e40af' }}>🚦 Busiest Traffic Path</h4>
            <p style={{ margin: 0, fontSize: '18px', fontWeight: 'bold' }}>
              {analysisData.path_analysis.busiest_path.path_name}
            </p>
            <p style={{ margin: '4px 0 0 0', color: '#666' }}>
              {analysisData.path_analysis.busiest_path.vehicle_count} vehicles
            </p>
          </div>
        )}

        {/* Path Breakdown */}
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ marginBottom: '12px' }}>Path-by-Path Breakdown</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px' }}>
            {Object.entries(analysisData.path_analysis.path_details).map(([pathId, pathData]) => (
              <div key={pathId} style={{
                padding: '12px',
                backgroundColor: '#f8fafc',
                borderRadius: '6px',
                borderLeft: `4px solid ${
                  pathId === 'P1' ? '#00ff00' :
                  pathId === 'P2' ? '#ffff00' :
                  pathId === 'P3' ? '#0000ff' :
                  pathId === 'P4' ? '#ff00ff' :
                  pathId === 'P5' ? '#ffa500' :
                  '#800080'
                }`
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: '600', fontSize: '16px' }}>{pathId}</span>
                  <span style={{ fontWeight: 'bold', color: '#3b82f6' }}>{pathData.count}</span>
                </div>
                <div style={{ fontSize: '14px', color: '#666', marginTop: '4px' }}>
                  {pathData.name}
                </div>
                <div style={{ fontSize: '12px', color: '#999', marginTop: '4px' }}>
                  {pathData.percentage.toFixed(1)}% of total flow
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Traffic Flow Insights */}
        {analysisData.traffic_metrics && (
          <div style={{
            padding: '16px',
            backgroundColor: '#f0fff4',
            borderRadius: '8px',
            border: '1px solid #d1fae5'
          }}>
            <h4 style={{ margin: '0 0 8px 0', color: '#065f46' }}>📊 Traffic Flow Insights</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <div>
                <strong>Dominant Flow:</strong> {analysisData.traffic_metrics.dominant_flow}
              </div>
              <div>
                <strong>Congestion Level:</strong> 
                <span style={{
                  padding: '2px 8px',
                  borderRadius: '12px',
                  fontSize: '12px',
                  fontWeight: '600',
                  marginLeft: '8px',
                  backgroundColor: 
                    analysisData.traffic_metrics.congestion_level.includes('Severe') ? '#fee2e2' :
                    analysisData.traffic_metrics.congestion_level.includes('High') ? '#fef3c7' :
                    analysisData.traffic_metrics.congestion_level.includes('Moderate') ? '#d1fae5' : '#f3f4f6',
                  color: 
                    analysisData.traffic_metrics.congestion_level.includes('Severe') ? '#dc2626' :
                    analysisData.traffic_metrics.congestion_level.includes('High') ? '#d97706' :
                    analysisData.traffic_metrics.congestion_level.includes('Moderate') ? '#065f46' : '#6b7280'
                }}>
                  {analysisData.traffic_metrics.congestion_level}
                </span>
              </div>
              <div>
                <strong>Efficiency Ratio:</strong> {analysisData.traffic_metrics.efficiency_ratio.toFixed(2)}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const handleVideoError = (e) => {
    console.error('Video playback error:', e);
    console.error('Video element error details:', {
      error: videoRef.current?.error,
      networkState: videoRef.current?.networkState,
      readyState: videoRef.current?.readyState
    });
    setVideoLoadError('Error playing video. The video file may be corrupted, still processing, or the format is not supported.');
  };

  const handleDownloadVideo = () => {
    const downloadUrl = type === 'session' 
      ? `http://127.0.0.1:8000/api/session-video/${videoId}/download/`
      : `http://127.0.0.1:8000/api/video/${videoId}/download/`;
    window.open(downloadUrl, '_blank');
  };

  const handleTryAlternativeView = () => {
    const alternativeUrl = type === 'session'
      ? `http://127.0.0.1:8000/api/session-video/${videoId}/direct/`
      : `http://127.0.0.1:8000/api/video/${videoId}/direct/`;
    console.log('🔄 Trying alternative video URL:', alternativeUrl);
    setVideoUrl(alternativeUrl);
    setVideoLoadError(null);
  };

  // Export functions
  const handleExportCSV = () => {
    const exportUrl = type === 'session'
      ? `http://127.0.0.1:8000/api/export/session/${videoId}/csv/`
      : `http://127.0.0.1:8000/api/export/${videoId}/csv/`;
    window.open(exportUrl, '_blank');
  };

  const handleExportPDF = () => {
    const exportUrl = type === 'session'
      ? `http://127.0.0.1:8000/api/export/session/${videoId}/pdf/`
      : `http://127.0.0.1:8000/api/export/${videoId}/pdf/`;
    window.open(exportUrl, '_blank');
  };

  const handleExportExcel = () => {
    const exportUrl = type === 'session'
      ? `http://127.0.0.1:8000/api/export/session/${videoId}/excel/`
      : `http://127.0.0.1:8000/api/export/${videoId}/excel/`;
    window.open(exportUrl, '_blank');
  };

  // Update the header and info display based on type
  const renderHeaderAndInfo = () => {
    if (type === 'session') {
      return (
        <>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 4px 0' }}>
            Session Analysis: {itemInfo?.name || "Loading..."}
          </h1>
          {itemInfo && (
            <p style={{ color: '#666', margin: 0 }}>
              Location: {itemInfo.location_details?.display_name || itemInfo.location || "Unknown"} •
              Videos: {itemInfo.video_files_count || 0} •
              Period: {itemInfo.start_datetime ? new Date(itemInfo.start_datetime).toLocaleDateString() : "Unknown"} to {itemInfo.end_datetime ? new Date(itemInfo.end_datetime).toLocaleDateString() : "Unknown"}
            </p>
          )}
        </>
      );
    } else { // type === 'video'
      return (
        <>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 4px 0' }}>
            Processed Video Analysis
          </h1>
          {itemInfo?.video_info && (
            <p style={{ color: '#666', margin: 0 }}>
              {itemInfo.video_info.filename} • Uploaded: {new Date(itemInfo.video_info.uploaded_at).toLocaleDateString()}
            </p>
          )}
          {!itemInfo?.video_info && itemInfo?.filename && (
            <p style={{ color: '#666', margin: 0 }}>
              {itemInfo.filename} • Uploaded: {new Date(itemInfo.uploaded_at).toLocaleDateString()}
            </p>
          )}
        </>
      );
    }
  };

  // Simple loading component
  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading {type} analysis data...</div>
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
        {renderHeaderAndInfo()}
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
      {analysisData && analysisData.summary && (
        <div className="dashboard-card" style={{ marginBottom: '24px' }}>
          <h3 style={{ marginBottom: '16px' }}>Analysis Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
                {analysisData.summary.total_vehicles || 0}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Total Vehicles</div>
            </div>

            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
                {analysisData.metadata?.processing_time ? analysisData.metadata.processing_time.toFixed(1) : 0}s
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Processing Time</div>
            </div>

            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: analysisData.metrics?.congestion_level === 'high' ? '#ef4444' : '#f59e0b' }}>
                {analysisData.metrics?.congestion_level || 'Unknown'}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Congestion Level</div>
            </div>

            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#8b5cf6' }}>
                {analysisData.metrics?.traffic_pattern || 'Unknown'}
              </div>
              <div style={{ fontSize: '14px', color: '#666' }}>Traffic Pattern</div>
            </div>
          </div>

          {/* Vehicle Breakdown */}
          {analysisData.summary.vehicle_breakdown && (
            <div>
              <h4 style={{ marginBottom: '12px' }}>Vehicle Breakdown</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
                {Object.entries(analysisData.summary.vehicle_breakdown).map(([vehicleType, count]) => (
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

      {/* Y-Junction Analysis */}
      {analysisData && analysisData.path_analysis && renderYJunctionAnalysis(analysisData)}

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
        <h3 style={{ marginBottom: '16px' }}>Processed {type === 'session' ? 'Session' : 'Video'} with Detection Overlay</h3>
        
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
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#666' }}>
                Component rendering with URL. Video element managed via React ref.
              </p>
            </div>

            {/* Video element with ref management */}
            <video
              ref={videoRef}
              controls
              style={{
                width: '100%',
                maxHeight: '70vh',
                border: '2px solid #e5e7eb',
                borderRadius: '8px',
                backgroundColor: '#000'
              }}
              onError={handleVideoError}
              onLoadStart={() => console.log('🎬 Video loading started')}
              onCanPlay={() => console.log('✅ Video can play')}
              onWaiting={() => console.log('⏳ Video waiting')}
              onPlaying={() => console.log('▶️ Video playing')}
              onPause={() => console.log('⏸️ Video paused')}
              onEnded={() => console.log('🏁 Video ended')}
              preload="metadata"
            >
              {/* Fallback source for browsers that don't work well with ref management */}
              <source src={videoUrl} type="video/mp4" />
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
                    <button 
                      onClick={() => videoRef.current?.load()}
                      style={{
                        padding: '8px 16px',
                        border: '1px solid #f59e0b',
                        borderRadius: '4px',
                        backgroundColor: 'white',
                        color: '#f59e0b',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      Reload Video
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
            <div style={{ fontSize: '16px', color: '#666', marginBottom: '16px' }}>
              Processed {type} video not available
            </div>
            <p style={{ color: '#999', fontSize: '14px', marginBottom: '20px' }}>
              The processed video with detection overlays is not available for this {type}.
              This could be because the {type} is still processing or there was an issue during processing.
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
              <li><strong>High confidence scores</strong> ({'>'}0.7 is good)</li>
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