// src/pages/GroupAnalysisDetail.js - ESLint-FIXED
import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";

function GroupAnalysisDetail() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const [groupData, setGroupData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchGroupAnalysis = useCallback(async () => {
    if (!groupId) return;
    
    try {
      setLoading(true);
      console.log(`🔄 Fetching analysis for group: ${groupId}`);
      const response = await axios.get(`http://127.0.0.1:8000/api/groups/${groupId}/analysis/`);
      setGroupData(response.data);
      setError(null);
      console.log("✅ Group analysis loaded successfully");
    } catch (err) {
      console.error("❌ Error fetching group analysis:", err);
      setError("Failed to load group analysis");
    } finally {
      setLoading(false);
    }
  }, [groupId]);

  const viewVideoAnalysis = useCallback((videoId) => {
    window.open(`/analysis?video=${videoId}`, '_blank');
  }, []);

  useEffect(() => {
    fetchGroupAnalysis();
  }, [fetchGroupAnalysis]);

  if (loading) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading group analysis...</div>
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
            onClick={() => navigate('/group-analysis')}
            style={{
              padding: '10px 20px',
              border: '1px solid #3b82f6',
              borderRadius: '4px',
              backgroundColor: '#3b82f6',
              color: 'white',
              cursor: 'pointer'
            }}
          >
            Back to Groups
          </button>
        </div>
      </div>
    );
  }

  if (!groupData) {
    return null;
  }

  // Safe destructuring with fallbacks
  const {
    group = {},
    aggregated_analysis = {},
    video_analyses = []
  } = groupData;

  return (
    <div className="main-content">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '32px' }}>
        <div>
          <button
            onClick={() => navigate('/group-analysis')}
            style={{
              padding: '8px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: 'white',
              cursor: 'pointer',
              marginBottom: '16px'
            }}
          >
            ← Back to Groups
          </button>
          <h1 style={{ fontSize: '28px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
            {group.name || 'Unknown Group'}
          </h1>
          <p style={{ color: '#666', margin: 0 }}>
            {group.location?.name || 'Unknown Location'} • {group.date || 'Unknown Date'} • {aggregated_analysis.time_range || 'No time range'}
          </p>
          {group.description && (
            <p style={{ color: '#666', margin: '8px 0 0 0', fontStyle: 'italic' }}>
              {group.description}
            </p>
          )}
        </div>
      </div>

      {/* Aggregated Analysis Summary */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <h2 style={{ marginBottom: '20px' }}>Aggregated Analysis</h2>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
          <div style={{ textAlign: 'center', padding: '20px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#3b82f6' }}>
              {aggregated_analysis.total_vehicles || 0}
            </div>
            <div style={{ fontSize: '14px', color: '#666' }}>Total Vehicles</div>
          </div>

          <div style={{ textAlign: 'center', padding: '20px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>
              {aggregated_analysis.video_count || 0}
            </div>
            <div style={{ fontSize: '14px', color: '#666' }}>Videos</div>
          </div>

          <div style={{ textAlign: 'center', padding: '20px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#f59e0b' }}>
              {Math.round(aggregated_analysis.total_processing_time || 0)}s
            </div>
            <div style={{ fontSize: '14px', color: '#666' }}>Processing Time</div>
          </div>

          <div style={{ textAlign: 'center', padding: '20px', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>
              {aggregated_analysis.peak_traffic || 0}
            </div>
            <div style={{ fontSize: '14px', color: '#666' }}>Peak Traffic</div>
          </div>
        </div>

        {/* Vehicle Breakdown */}
        <div>
          <h3 style={{ marginBottom: '16px' }}>Vehicle Breakdown</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#3b82f6' }}>
                {aggregated_analysis.car_count || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Cars</div>
            </div>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#f59e0b' }}>
                {aggregated_analysis.truck_count || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Trucks</div>
            </div>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#ef4444' }}>
                {aggregated_analysis.motorcycle_count || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Motorcycles</div>
            </div>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#8b5cf6' }}>
                {aggregated_analysis.bus_count || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Buses</div>
            </div>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#10b981' }}>
                {aggregated_analysis.bicycle_count || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Bicycles</div>
            </div>
            <div style={{ textAlign: 'center', padding: '16px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
              <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#6b7280' }}>
                {aggregated_analysis.other_count || 0}
              </div>
              <div style={{ fontSize: '12px', color: '#666' }}>Others</div>
            </div>
          </div>
        </div>
      </div>

      {/* Individual Video Analyses */}
      <div className="dashboard-card">
        <h2 style={{ marginBottom: '20px' }}>Video Analyses ({video_analyses.length})</h2>
        
        <div style={{ display: 'grid', gap: '16px' }}>
          {video_analyses.map((analysis) => (
            <div key={analysis.video_id} style={{
              padding: '20px',
              backgroundColor: '#f8fafc',
              borderRadius: '8px',
              border: '1px solid #e5e7eb'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ margin: '0 0 8px 0', color: '#1f2937' }}>
                    {analysis.title || analysis.filename || 'Untitled Video'}
                  </h3>
                  <p style={{ color: '#6b7280', margin: '0 0 8px 0', fontSize: '14px' }}>
                    {analysis.start_time || 'Unknown'} - {analysis.end_time || 'Unknown'} • 
                    {analysis.duration ? ` ${Math.round(analysis.duration / 60)}min` : ''}
                  </p>
                </div>
                <button
                  onClick={() => viewVideoAnalysis(analysis.video_id)}
                  style={{
                    padding: '8px 16px',
                    border: '1px solid #3b82f6',
                    borderRadius: '4px',
                    backgroundColor: 'white',
                    color: '#3b82f6',
                    cursor: 'pointer',
                    fontSize: '14px'
                  }}
                >
                  View Analysis
                </button>
              </div>

              <div style={{ display: 'flex', gap: '24px', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#6b7280', fontSize: '14px' }}>🚗</span>
                  <span style={{ fontSize: '14px', fontWeight: '500' }}>{analysis.total_vehicles || 0} vehicles</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ color: '#6b7280', fontSize: '14px' }}>⏱️</span>
                  <span style={{ fontSize: '14px', fontWeight: '500' }}>{analysis.processing_time || 0}s processing</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ 
                    backgroundColor: 
                      analysis.congestion_level === 'high' ? '#fee2e2' :
                      analysis.congestion_level === 'medium' ? '#fef3c7' : '#d1fae5',
                    color: 
                      analysis.congestion_level === 'high' ? '#dc2626' :
                      analysis.congestion_level === 'medium' ? '#d97706' : '#065f46',
                    padding: '4px 8px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    fontWeight: '600'
                  }}>
                    {(analysis.congestion_level || 'low').toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Vehicle breakdown for this video */}
              <div style={{ marginTop: '12px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                {analysis.vehicle_breakdown && Object.entries(analysis.vehicle_breakdown).map(([type, count]) => (
                  count > 0 && (
                    <span key={type} style={{
                      fontSize: '12px',
                      color: '#6b7280',
                      backgroundColor: '#f3f4f6',
                      padding: '4px 8px',
                      borderRadius: '4px'
                    }}>
                      {type}: {count}
                    </span>
                  )
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default GroupAnalysisDetail;