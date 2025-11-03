// src/components/LocationGroupManager.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import CreateGroupModal from './CreateGroupModal';

const LocationGroupManager = () => {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [ungroupedVideos, setUngroupedVideos] = useState([]);

  const fetchGroups = async () => {
    try {
      setLoading(true);
      const [groupsResponse, ungroupedResponse] = await Promise.all([
        axios.get('http://127.0.0.1:8000/api/location-groups/with-videos/'),
        axios.get('http://127.0.0.1:8000/api/videos/ungrouped/')
      ]);
      setGroups(groupsResponse.data);
      setUngroupedVideos(ungroupedResponse.data);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const autoGroupVideos = async () => {
    try {
      setLoading(true);
      const response = await axios.post('http://127.0.0.1:8000/api/location-groups/auto-group/');
      alert(`Auto-grouping completed: ${response.data.message}`);
      fetchGroups();
    } catch (error) {
      console.error('Error auto-grouping:', error);
      alert('Error auto-grouping videos');
    } finally {
      setLoading(false);
    }
  };

  const handleGroupCreated = (newGroup) => {
    alert('Location group created successfully!');
    fetchGroups(); // Refresh the list
  };

  const addVideosToGroup = async (group, videoIds) => {
    try {
      await axios.post(`http://127.0.0.1:8000/api/location-groups/${group.id}/videos/`, {
        video_ids: videoIds
      });
      alert(`Added ${videoIds.length} videos to group`);
      fetchGroups();
    } catch (error) {
      console.error('Error adding videos to group:', error);
      alert(`Error: ${error.response?.data?.error || error.message}`);
    }
  };

  const removeVideosFromGroup = async (group, videoIds) => {
    try {
      await axios.delete(`http://127.0.0.1:8000/api/location-groups/${group.id}/videos/`, {
        data: { video_ids: videoIds }
      });
      alert(`Removed ${videoIds.length} videos from group`);
      fetchGroups();
    } catch (error) {
      console.error('Error removing videos from group:', error);
      alert(`Error: ${error.response?.data?.error || error.message}`);
    }
  };

  useEffect(() => {
    fetchGroups();
  }, []);

  if (loading && groups.length === 0) {
    return (
      <div className="main-content">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '18px', color: '#666', marginBottom: '16px' }}>Loading groups...</div>
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

  return (
    <div className="main-content">
      <CreateGroupModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onGroupCreated={handleGroupCreated}
      />

      <header style={{ marginBottom: '32px' }}>
        <h1>Location-Date Groups</h1>
        <p>Organize processed videos by location and recording date</p>
      </header>

      {/* Quick Stats and Actions */}
      <div className="dashboard-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h3 style={{ margin: '0 0 8px 0' }}>Group Overview</h3>
            <p style={{ color: '#666', margin: 0, fontSize: '14px' }}>
              {groups.length} Groups • {ungroupedVideos.length} Ungrouped Videos • 
              Total Videos: {groups.reduce((total, group) => total + group.video_count, 0)}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button 
              onClick={() => setIsCreateModalOpen(true)}
              style={{
                padding: '10px 20px',
                border: '1px solid #3b82f6',
                borderRadius: '6px',
                backgroundColor: '#3b82f6',
                color: 'white',
                cursor: 'pointer',
                fontWeight: '500'
              }}
            >
              + Create New Group
            </button>
            
            <button 
              onClick={autoGroupVideos}
              disabled={loading || ungroupedVideos.length === 0}
              style={{
                padding: '10px 20px',
                border: '1px solid #10b981',
                borderRadius: '6px',
                backgroundColor: ungroupedVideos.length === 0 ? '#f3f4f6' : '#10b981',
                color: ungroupedVideos.length === 0 ? '#9ca3af' : 'white',
                cursor: ungroupedVideos.length === 0 ? 'not-allowed' : 'pointer',
                fontWeight: '500'
              }}
            >
              Auto-Group All Videos
            </button>
          </div>
        </div>

        {ungroupedVideos.length > 0 && (
          <div style={{
            marginTop: '16px',
            padding: '12px',
            backgroundColor: '#f0f9ff',
            border: '1px solid #bae6fd',
            borderRadius: '6px'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: '#0369a1', fontSize: '14px' }}>
                📹 {ungroupedVideos.length} videos available for grouping
              </span>
              <button
                onClick={() => {
                  const videoIds = ungroupedVideos.map(v => v.id);
                  if (videoIds.length > 0 && groups.length > 0) {
                    addVideosToGroup(groups[0], videoIds.slice(0, 5)); // Add to first group as example
                  }
                }}
                style={{
                  padding: '6px 12px',
                  border: '1px solid #0369a1',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  color: '#0369a1',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Add to First Group
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Groups List */}
      {groups.length === 0 ? (
        <div className="dashboard-card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px', color: '#d1d5db' }}>📁</div>
          <h3 style={{ marginBottom: '12px', color: '#374151' }}>No Groups Yet</h3>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>
            Create your first location group to organize videos by location and date.
          </p>
          <button 
            onClick={() => setIsCreateModalOpen(true)}
            style={{
              padding: '12px 24px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: '#3b82f6',
              color: 'white',
              cursor: 'pointer',
              fontWeight: '500',
              fontSize: '16px'
            }}
          >
            Create Your First Group
          </button>
        </div>
      ) : (
        <div>
          {groups.map(group => (
            <div key={group.id} className="dashboard-card" style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '16px' }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ margin: '0 0 8px 0', color: '#1f2937' }}>
                    {group.location.name} - {group.date}
                  </h3>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{ color: '#6b7280', fontSize: '14px' }}>
                      🕒 {group.time_range}
                    </span>
                    <span style={{ color: '#6b7280', fontSize: '14px' }}>
                      📹 {group.video_count} videos
                    </span>
                    <span style={{ color: '#6b7280', fontSize: '14px' }}>
                      🚗 {group.total_vehicles} total vehicles
                    </span>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button 
                    onClick={() => setSelectedGroup(selectedGroup?.id === group.id ? null : group)}
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
                    {selectedGroup?.id === group.id ? 'Hide Videos' : 'Show Videos'}
                  </button>
                  
                  <button
                    onClick={() => window.open(`/analysis?group=${group.id}`, '_blank')}
                    style={{
                      padding: '8px 16px',
                      border: '1px solid #10b981',
                      borderRadius: '4px',
                      backgroundColor: 'white',
                      color: '#10b981',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    View Analysis
                  </button>
                </div>
              </div>

              {selectedGroup?.id === group.id && (
                <div>
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    marginBottom: '16px',
                    paddingBottom: '12px',
                    borderBottom: '1px solid #e5e7eb'
                  }}>
                    <h4 style={{ margin: 0 }}>Videos (Sorted by Time)</h4>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => {
                          const videoIds = group.videos.map(v => v.id);
                          removeVideosFromGroup(group, videoIds.slice(0, 2)); // Remove first 2 as example
                        }}
                        style={{
                          padding: '6px 12px',
                          border: '1px solid #ef4444',
                          borderRadius: '4px',
                          backgroundColor: 'white',
                          color: '#ef4444',
                          cursor: 'pointer',
                          fontSize: '12px'
                        }}
                      >
                        Remove Some Videos
                      </button>
                    </div>
                  </div>
                  
                  <div style={{ display: 'grid', gap: '12px' }}>
                    {group.videos.map(video => (
                      <div key={video.id} style={{
                        padding: '16px',
                        backgroundColor: '#f8fafc',
                        borderRadius: '6px',
                        border: '1px solid #e5e7eb'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                              {video.title || video.filename}
                            </div>
                            <div style={{ fontSize: '14px', color: '#6b7280' }}>
                              {video.start_time} - {video.end_time} • 
                              {video.duration ? ` ${Math.round(video.duration / 60)}min` : ''} • 
                              {video.vehicle_count ? ` ${video.vehicle_count} vehicles` : ''}
                            </div>
                          </div>
                          <button 
                            onClick={() => window.open(`/analysis?video=${video.id}`, '_blank')}
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
                            View Analysis
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default LocationGroupManager;