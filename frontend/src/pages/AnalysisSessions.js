// src/pages/AnalysisSessions.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const AnalysisSessions = () => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newSession, setNewSession] = useState({
    name: '',
    location: '',
    start_datetime: '',
    end_datetime: ''
  });
  const [locations, setLocations] = useState([]);

  const navigate = useNavigate();

  useEffect(() => {
    fetchSessions();
    fetchLocationsForSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      setLoading(true);
      const response = await axios.get('http://127.0.0.1:8000/api/sessions/');
      setSessions(response.data);
    } catch (err) {
      console.error('Error fetching sessions:', err);
      setError('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  const fetchLocationsForSessions = async () => {
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/locations/');
      setLocations(response.data);
    } catch (error) {
      console.error('Error fetching locations for sessions:', error);
    }
  };

  const handleCreateSession = async (e) => {
    e.preventDefault();
    if (!newSession.name || !newSession.location || !newSession.start_datetime || !newSession.end_datetime) {
      alert('Please fill in all fields.');
      return;
    }
    try {
      await axios.post('http://127.0.0.1:8000/api/sessions/', newSession);
      setNewSession({ name: '', location: '', start_datetime: '', end_datetime: '' });
      fetchSessions();
    } catch (error) {
      console.error('Error creating session:', error);
      alert('Failed to create session: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setNewSession(prev => ({ ...prev, [name]: value }));
  };

  const handleProcessSession = async (sessionId) => {
    if (window.confirm("Are you sure you want to start processing this session? This will concatenate videos and run analysis.")) {
      try {
        await axios.post(`http://127.0.0.1:8000/api/sessions/${sessionId}/process/`);
        alert('Session processing started!');
        fetchSessions();
      } catch (error) {
        console.error('Error starting session processing:', error);
        alert('Failed to start processing: ' + (error.response?.data?.error || error.message));
      }
    }
  };

  // 🔥 UPDATED: Enhanced quick process handler with response message
  const handleQuickProcess = async (sessionId) => {
    try {
      const response = await axios.post(`http://127.0.0.1:8000/api/sessions/${sessionId}/quick-process/`);
      
      alert(`✅ ${response.data.message || 'Session processing started! Videos processing in parallel.'}`);
      console.log('Quick process started:', response.data);
      
      fetchSessions(); // Refresh the list
    } catch (error) {
      console.error('Quick process error:', error);
      alert(`❌ Error: ${error.response?.data?.error || error.message}`);
    }
  };

  if (loading) return <div className="main-content">Loading sessions...</div>;
  if (error) return <div className="main-content">Error: {error}</div>;

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Analysis Sessions
        </h1>
        <p style={{ color: '#666', margin: 0 }}>Group and process multiple video clips together.</p>
      </header>

      {/* Create New Session Form */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Create New Session</h2>
        <form onSubmit={handleCreateSession}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>Session Name *</label>
              <input
                type="text"
                name="name"
                value={newSession.name}
                onChange={handleInputChange}
                required
                style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px' }}
                placeholder="e.g., Baliwasan Daytime Coverage 2024-05-20"
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>Location *</label>
              <select
                name="location"
                value={newSession.location}
                onChange={handleInputChange}
                required
                style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px', backgroundColor: 'white' }}
              >
                <option value="">Select a location</option>
                {locations.map(loc => (
                  <option key={loc.id} value={loc.id}>{loc.display_name}</option>
                ))}
              </select>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>Start Datetime *</label>
              <input
                type="datetime-local"
                name="start_datetime"
                value={newSession.start_datetime}
                onChange={handleInputChange}
                required
                style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>End Datetime *</label>
              <input
                type="datetime-local"
                name="end_datetime"
                value={newSession.end_datetime}
                onChange={handleInputChange}
                required
                style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '14px' }}
              />
            </div>
          </div>
          <button type="submit" style={{ padding: '10px 20px', border: 'none', borderRadius: '4px', backgroundColor: '#3b82f6', color: 'white', cursor: 'pointer' }}>
            Create Session
          </button>
        </form>
      </div>

      {/* Sessions List */}
      <div className="dashboard-card">
        <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>Existing Sessions</h2>
        {sessions.length === 0 ? (
          <p>No sessions found.</p>
        ) : (
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Location</th>
                  <th>Date Range</th>
                  <th>Status</th>
                  <th>Videos</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map(session => (
                  <tr key={session.id}>
                    <td style={{ fontWeight: '600' }}>{session.name}</td>
                    <td>{session.location_details?.display_name || session.location}</td>
                    <td>
                      {new Date(session.start_datetime).toLocaleDateString('en-US', { 
                        timeZone: 'UTC',
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit'
                      })} - 
                      {new Date(session.end_datetime).toLocaleDateString('en-US', { 
                        timeZone: 'UTC',
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit'
                      })}
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        padding: '4px 8px',
                        borderRadius: '12px',
                        fontSize: '12px',
                        fontWeight: '600',
                        backgroundColor:
                          session.status === 'completed' ? '#d1fae5' :
                          session.status === 'processing' ? '#fef3c7' :
                          session.status === 'failed' ? '#fee2e2' : '#f3f4f6',
                        color:
                          session.status === 'completed' ? '#065f46' :
                          session.status === 'processing' ? '#d97706' :
                          session.status === 'failed' ? '#991b1b' : '#6b7280'
                      }}>
                        {session.status}
                      </span>
                    </td>
                    <td>{session.video_files_count}</td>
                    <td>
                      {/* ✅ UPDATED ACTION BUTTONS */}
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {session.status === 'pending_upload' && (
                          <>
                            <button
                              onClick={() => handleQuickProcess(session.id)}
                              style={{
                                padding: '6px 12px',
                                border: 'none',
                                borderRadius: '4px',
                                backgroundColor: '#10b981',
                                color: 'white',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: 'bold'
                              }}
                            >
                              🚀 Quick Process
                            </button>
                            
                            <button
                              onClick={() => handleProcessSession(session.id)}
                              style={{
                                padding: '6px 12px',
                                border: '1px solid #3b82f6',
                                borderRadius: '4px',
                                backgroundColor: 'white',
                                color: '#3b82f6',
                                cursor: 'pointer',
                                fontSize: '12px'
                              }}
                            >
                              Process Session
                            </button>
                          </>
                        )}

                        {session.status === 'processing' && (
                          <span style={{
                            padding: '4px 8px',
                            backgroundColor: '#fef3c7',
                            color: '#d97706',
                            borderRadius: '4px',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}>
                            ⏳ Processing...
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalysisSessions;