// src/pages/Settings.js
import React, { useState, useEffect } from "react";
import axios from "axios";

function Settings() {
  const [darkMode, setDarkMode] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const [language, setLanguage] = useState("en");
  const [activeTab, setActiveTab] = useState("general"); // "general", "locations", or "profiles"
  
  // Location Management State
  const [locations, setLocations] = useState([]);
  const [locationLoading, setLocationLoading] = useState(true);
  const [editingLocation, setEditingLocation] = useState(null);
  const [showLocationForm, setShowLocationForm] = useState(false);
  const [locationFormData, setLocationFormData] = useState({
    name: '',
    display_name: '',
    description: '',
    latitude: '',
    longitude: '',
    processing_profile: '',
    detection_config: {},
    active: true
  });

  // Processing Profile Management State
  const [processingProfiles, setProcessingProfiles] = useState([]);
  const [profileLoading, setProfileLoading] = useState(true);
  const [editingProfile, setEditingProfile] = useState(null);
  const [showProfileForm, setShowProfileForm] = useState(false);
  const [profileFormData, setProfileFormData] = useState({
    name: '',
    display_name: '',
    description: '',
    detector_class: 'RTXVehicleDetector',
    detector_module: 'ml.vehicle_detector',
    config_parameters: {},
    road_type: 'generic',
    active: true
  });

  // Available road types for processing profiles
  const roadTypes = [
    { value: 'highway', label: 'Highway' },
    { value: 'intersection', label: 'Intersection' },
    { value: 'y_junction', label: 'Y-Junction' },
    { value: 't_intersection', label: 'T-Intersection' },
    { value: 'roundabout', label: 'Roundabout' },
    { value: 'urban', label: 'Urban Street' },
    { value: 'generic', label: 'Generic' },
    { value: 'custom', label: 'Custom' }
  ];

  // Available detector classes (you can expand this list)
  const detectorClasses = [
    { value: 'RTXVehicleDetector', label: 'Standard Vehicle Detector' },
    { value: 'BaliwasanYJunctionDetector', label: 'Baliwasan Y-Junction Detector' }
    // Add more detector classes as you create them
  ];

  useEffect(() => {
    if (activeTab === "locations") {
      fetchLocations();
      fetchProcessingProfiles(); // Need profiles for the dropdown
    } else if (activeTab === "profiles") {
      fetchProcessingProfiles();
    }
  }, [activeTab]);

  // Location Management Functions
  const fetchLocations = async () => {
    try {
      setLocationLoading(true);
      console.log("🔄 Fetching locations...");
      const response = await axios.get("http://127.0.0.1:8000/api/locations/");
      console.log("✅ Locations fetched:", response.data);
      setLocations(response.data);
    } catch (error) {
      console.error("❌ Error fetching locations:", error);
      alert('Failed to load locations. Please check if the server is running.');
    } finally {
      setLocationLoading(false);
    }
  };

  const fetchProcessingProfiles = async () => {
    try {
      setProfileLoading(true);
      console.log("🔄 Fetching processing profiles...");
      const response = await axios.get("http://127.0.0.1:8000/api/processing-profiles/");
      console.log("✅ Processing profiles fetched:", response.data);
      setProcessingProfiles(response.data);
    } catch (error) {
      console.error("❌ Error fetching processing profiles:", error);
      alert('Failed to load processing profiles.');
    } finally {
      setProfileLoading(false);
    }
  };

  const handleLocationInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setLocationFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleProfileInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setProfileFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleLocationSubmit = async (e) => {
    e.preventDefault();
    try {
      let response;
      
      console.log("🔄 Submitting location data:", locationFormData);
      console.log("📝 Editing location:", editingLocation);

      if (editingLocation) {
        response = await axios.put(`http://127.0.0.1:8000/api/locations/${editingLocation.id}/`, locationFormData);
        console.log("✅ Location update response:", response.data);
      } else {
        response = await axios.post('http://127.0.0.1:8000/api/locations/', locationFormData);
        console.log("✅ Location create response:", response.data);
      }
      
      setShowLocationForm(false);
      setEditingLocation(null);
      setLocationFormData({
        name: '',
        display_name: '',
        description: '',
        latitude: '',
        longitude: '',
        processing_profile: '',
        detection_config: {},
        active: true
      });
      
      setTimeout(() => {
        fetchLocations();
      }, 500);
      
      alert(editingLocation ? 'Location updated successfully!' : 'Location created successfully!');
      
    } catch (error) {
      console.error('❌ Error saving location:', error);
      console.error('❌ Error response:', error.response);
      
      if (error.response?.data) {
        alert('Error saving location: ' + JSON.stringify(error.response.data));
      } else {
        alert('Error saving location: ' + error.message);
      }
    }
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    try {
      let response;
      
      console.log("🔄 Submitting profile data:", profileFormData);
      console.log("📝 Editing profile:", editingProfile);

      if (editingProfile) {
        response = await axios.put(`http://127.0.0.1:8000/api/processing-profiles/${editingProfile.id}/`, profileFormData);
        console.log("✅ Profile update response:", response.data);
      } else {
        response = await axios.post('http://127.0.0.1:8000/api/processing-profiles/', profileFormData);
        console.log("✅ Profile create response:", response.data);
      }
      
      setShowProfileForm(false);
      setEditingProfile(null);
      setProfileFormData({
        name: '',
        display_name: '',
        description: '',
        detector_class: 'RTXVehicleDetector',
        detector_module: 'ml.vehicle_detector',
        config_parameters: {},
        road_type: 'generic',
        active: true
      });
      
      setTimeout(() => {
        fetchProcessingProfiles();
      }, 500);
      
      alert(editingProfile ? 'Processing profile updated successfully!' : 'Processing profile created successfully!');
      
    } catch (error) {
      console.error('❌ Error saving profile:', error);
      console.error('❌ Error response:', error.response);
      
      if (error.response?.data) {
        alert('Error saving profile: ' + JSON.stringify(error.response.data));
      } else {
        alert('Error saving profile: ' + error.message);
      }
    }
  };

  const handleEditLocation = (location) => {
    console.log("✏️ Editing location:", location);
    setEditingLocation(location);
    setLocationFormData({
      name: location.name || '',
      display_name: location.display_name || '',
      description: location.description || '',
      latitude: location.latitude || '',
      longitude: location.longitude || '',
      processing_profile: location.processing_profile || '',
      detection_config: location.detection_config || {},
      active: location.active !== undefined ? location.active : true
    });
    setShowLocationForm(true);
  };

  const handleEditProfile = (profile) => {
    console.log("✏️ Editing profile:", profile);
    setEditingProfile(profile);
    setProfileFormData({
      name: profile.name || '',
      display_name: profile.display_name || '',
      description: profile.description || '',
      detector_class: profile.detector_class || 'RTXVehicleDetector',
      detector_module: profile.detector_module || 'ml.vehicle_detector',
      config_parameters: profile.config_parameters || {},
      road_type: profile.road_type || 'generic',
      active: profile.active !== undefined ? profile.active : true
    });
    setShowProfileForm(true);
  };

  const handleDeleteLocation = async (location) => {
    if (window.confirm(`Are you sure you want to delete "${location.display_name}"?`)) {
      try {
        console.log(`🗑️ Deleting location ID: ${location.id}`);
        await axios.delete(`http://127.0.0.1:8000/api/locations/${location.id}/`);
        console.log("✅ Location deleted successfully");
        fetchLocations();
      } catch (error) {
        console.error('❌ Error deleting location:', error);
        alert('Error deleting location: ' + (error.response?.data?.error || error.message));
      }
    }
  };

  const handleDeleteProfile = async (profile) => {
    if (window.confirm(`Are you sure you want to delete "${profile.display_name}"? This will fail if any locations are using this profile.`)) {
      try {
        console.log(`🗑️ Deleting profile ID: ${profile.id}`);
        await axios.delete(`http://127.0.0.1:8000/api/processing-profiles/${profile.id}/`);
        console.log("✅ Profile deleted successfully");
        fetchProcessingProfiles();
      } catch (error) {
        console.error('❌ Error deleting profile:', error);
        if (error.response?.data?.error) {
          alert('Error deleting profile: ' + error.response.data.error);
        } else {
          alert('Error deleting profile: ' + error.message);
        }
      }
    }
  };

  const cancelLocationEdit = () => {
    setShowLocationForm(false);
    setEditingLocation(null);
    setLocationFormData({
      name: '',
      display_name: '',
      description: '',
      latitude: '',
      longitude: '',
      processing_profile: '',
      detection_config: {},
      active: true
    });
  };

  const cancelProfileEdit = () => {
    setShowProfileForm(false);
    setEditingProfile(null);
    setProfileFormData({
      name: '',
      display_name: '',
      description: '',
      detector_class: 'RTXVehicleDetector',
      detector_module: 'ml.vehicle_detector',
      config_parameters: {},
      road_type: 'generic',
      active: true
    });
  };

  const getRoadTypeLabel = (roadTypeValue) => {
    const roadType = roadTypes.find(rt => rt.value === roadTypeValue);
    return roadType ? roadType.label : roadTypeValue;
  };

  const getDetectorClassLabel = (detectorClassValue) => {
    const detectorClass = detectorClasses.find(dc => dc.value === detectorClassValue);
    return detectorClass ? detectorClass.label : detectorClassValue;
  };

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Settings & Administration
        </h1>
        <p style={{ color: '#666' }}>Manage system settings, locations, and processing profiles</p>
      </header>

      {/* Tab Navigation */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ 
          display: 'flex', 
          borderBottom: '1px solid #e2e8f0',
          marginBottom: '24px'
        }}>
          <button
            onClick={() => setActiveTab("general")}
            style={{
              padding: '12px 24px',
              border: 'none',
              backgroundColor: 'transparent',
              color: activeTab === "general" ? '#3b82f6' : '#6b7280',
              borderBottom: activeTab === "general" ? '2px solid #3b82f6' : '2px solid transparent',
              cursor: 'pointer',
              fontWeight: activeTab === "general" ? '600' : '400',
              fontSize: '16px'
            }}
          >
            General Settings
          </button>
          <button
            onClick={() => setActiveTab("locations")}
            style={{
              padding: '12px 24px',
              border: 'none',
              backgroundColor: 'transparent',
              color: activeTab === "locations" ? '#3b82f6' : '#6b7280',
              borderBottom: activeTab === "locations" ? '2px solid #3b82f6' : '2px solid transparent',
              cursor: 'pointer',
              fontWeight: activeTab === "locations" ? '600' : '400',
              fontSize: '16px'
            }}
          >
            Location Management
          </button>
          <button
            onClick={() => setActiveTab("profiles")}
            style={{
              padding: '12px 24px',
              border: 'none',
              backgroundColor: 'transparent',
              color: activeTab === "profiles" ? '#3b82f6' : '#6b7280',
              borderBottom: activeTab === "profiles" ? '2px solid #3b82f6' : '2px solid transparent',
              cursor: 'pointer',
              fontWeight: activeTab === "profiles" ? '600' : '400',
              fontSize: '16px'
            }}
          >
            Processing Profiles
          </button>
        </div>
      </div>

      {/* General Settings Tab */}
      {activeTab === "general" && (
        <>
          <div className="dashboard-card" style={{ marginBottom: '32px' }}>
            <h2 className="section-title">Account Information</h2>
            
            <div className="table-container" style={{ marginBottom: '24px' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Email</th>
                    <th>Role</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>admin</td>
                    <td>admin@traffic.gov</td>
                    <td>Administrator</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="divider"></div>

            <div className="info-box">
              <h3 className="info-title">How to Use the System</h3>
              <ul style={{ color: '#4a5568', lineHeight: '1.5', listStyle: 'disc', paddingLeft: '20px' }}>
                <li style={{ marginBottom: '8px' }}><strong>Viewing Traffic Data</strong> - The Overview page displays weekly traffic patterns and daily vehicle counts. Data is collected automatically from our traffic cameras.</li>
                <li><strong>Analyzing Congestion</strong> - The Congestion Results page shows peak traffic hours for specific areas. Use this data to identify problem areas and optimize traffic flow.</li>
              </ul>
            </div>

            <div className="divider"></div>

            <h3 style={{ fontSize: '18px', fontWeight: '500', marginBottom: '16px' }}>Developers</h3>
            <p style={{ color: '#666', marginBottom: '24px' }}>Developed by Students of Western Mindanao State University (WMSU)</p>

            <div className="divider"></div>

            <h3 style={{ fontSize: '18px', fontWeight: '500', marginBottom: '16px' }}>Session</h3>
            <p style={{ color: '#666' }}>Logged in as Administrator</p>
          </div>

          <div className="dashboard-card">
            <h2 className="section-title">System Settings</h2>
            
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', padding: '16px 0' }}>
              <div>
                <p style={{ fontWeight: '500' }}>Dark Mode</p>
                <p style={{ fontSize: '14px', color: '#666' }}>Switch between light and dark themes</p>
              </div>
              <label style={{ display: 'inline-flex', alignItems: 'center', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={darkMode}
                  onChange={() => setDarkMode(!darkMode)}
                  style={{ position: 'absolute', opacity: 0 }}
                />
                <div style={{
                  width: '44px',
                  height: '24px',
                  backgroundColor: darkMode ? '#3b82f6' : '#e5e7eb',
                  borderRadius: '12px',
                  position: 'relative',
                  transition: 'background-color 0.2s'
                }}>
                  <span style={{
                    position: 'absolute',
                    left: '2px',
                    top: '2px',
                    backgroundColor: 'white',
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    transition: 'transform 0.2s',
                    transform: darkMode ? 'translateX(20px)' : 'translateX(0)'
                  }}></span>
                </div>
              </label>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', padding: '16px 0' }}>
              <div>
                <p style={{ fontWeight: '500' }}>Notifications</p>
                <p style={{ fontSize: '14px', color: '#666' }}>Receive alerts for traffic events</p>
              </div>
              <input
                type="checkbox"
                checked={notifications}
                onChange={() => setNotifications(!notifications)}
                style={{ width: '20px', height: '20px' }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 0' }}>
              <div>
                <p style={{ fontWeight: '500' }}>Language</p>
                <p style={{ fontSize: '14px', color: '#666' }}>Interface language preference</p>
              </div>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="select-input"
              >
                <option value="en">English</option>
                <option value="ph">Filipino</option>
                <option value="es">Spanish</option>
              </select>
            </div>

            <div style={{ marginTop: '24px', textAlign: 'center' }}>
              <button className="button button-primary">
                Save Changes
              </button>
            </div>
          </div>
        </>
      )}

      {/* Location Management Tab */}
      {activeTab === "locations" && (
        <>
          {/* Add Location Button */}
          <div style={{ marginBottom: '24px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setShowLocationForm(true)}
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
              + Add New Location
            </button>
            
            <button
              onClick={fetchLocations}
              style={{
                padding: '12px 24px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                color: '#374151',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '16px'
              }}
            >
              🔄 Refresh Locations
            </button>
          </div>

          {/* Location Form */}
          {showLocationForm && (
            <div className="dashboard-card" style={{ marginBottom: '24px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>
                {editingLocation ? 'Edit Location' : 'Add New Location'}
              </h2>
              
              <form onSubmit={handleLocationSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Internal Name *
                    </label>
                    <input
                      type="text"
                      name="name"
                      value={locationFormData.name}
                      onChange={handleLocationInputChange}
                      required
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px'
                      }}
                      placeholder="e.g., baliwasan_yjunction"
                    />
                  </div>
                  
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Display Name *
                    </label>
                    <input
                      type="text"
                      name="display_name"
                      value={locationFormData.display_name}
                      onChange={handleLocationInputChange}
                      required
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px'
                      }}
                      placeholder="e.g., Baliwasan Y-Junction"
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                    Description
                  </label>
                  <textarea
                    name="description"
                    value={locationFormData.description}
                    onChange={handleLocationInputChange}
                    rows="3"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px',
                      resize: 'vertical'
                    }}
                    placeholder="Description of this location..."
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Latitude
                    </label>
                    <input
                      type="number"
                      step="any"
                      name="latitude"
                      value={locationFormData.latitude}
                      onChange={handleLocationInputChange}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px'
                      }}
                      placeholder="e.g., 6.9214"
                    />
                  </div>
                  
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Longitude
                    </label>
                    <input
                      type="number"
                      step="any"
                      name="longitude"
                      value={locationFormData.longitude}
                      onChange={handleLocationInputChange}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px'
                      }}
                      placeholder="e.g., 122.0790"
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                    Processing Profile *
                  </label>
                  <select
                    name="processing_profile"
                    value={locationFormData.processing_profile}
                    onChange={handleLocationInputChange}
                    required
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px',
                      backgroundColor: 'white'
                    }}
                  >
                    <option value="">Select a processing profile</option>
                    {processingProfiles.map(profile => (
                      <option key={profile.id} value={profile.id}>
                        {profile.display_name} ({getRoadTypeLabel(profile.road_type)})
                      </option>
                    ))}
                  </select>
                  <p style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                    Choose the processing profile that best matches this location's characteristics
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
                  <input
                    type="checkbox"
                    name="active"
                    checked={locationFormData.active}
                    onChange={handleLocationInputChange}
                    style={{ marginRight: '8px' }}
                  />
                  <label style={{ fontWeight: '500' }}>Active Location</label>
                </div>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <button
                    type="submit"
                    style={{
                      padding: '10px 20px',
                      border: 'none',
                      borderRadius: '4px',
                      backgroundColor: '#10b981',
                      color: 'white',
                      cursor: 'pointer',
                      fontWeight: '500'
                    }}
                  >
                    {editingLocation ? 'Update Location' : 'Create Location'}
                  </button>
                  
                  <button
                    type="button"
                    onClick={cancelLocationEdit}
                    style={{
                      padding: '10px 20px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      backgroundColor: 'white',
                      color: '#374151',
                      cursor: 'pointer'
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Locations List */}
          <div className="dashboard-card">
            <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>
              Available Locations ({locations.length})
            </h2>
            
            {locationLoading ? (
              <div style={{ textAlign: 'center', padding: '40px' }}>
                <div style={{ fontSize: '16px', color: '#666' }}>Loading locations...</div>
              </div>
            ) : locations.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                No locations found. Add your first location to get started.
              </div>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Display Name</th>
                      <th>Internal Name</th>
                      <th>Processing Profile</th>
                      <th>Coordinates</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {locations.map(location => (
                      <tr key={location.id}>
                        <td style={{ fontWeight: '600' }}>{location.display_name}</td>
                        <td>
                          <code style={{ fontSize: '12px', backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '3px' }}>
                            {location.name}
                          </code>
                        </td>
                        <td>
                          <div>
                            <div style={{ fontWeight: '500' }}>
                              {location.processing_profile_details?.display_name || 'Unknown Profile'}
                            </div>
                            <div style={{ fontSize: '12px', color: '#666' }}>
                              {getRoadTypeLabel(location.processing_profile_details?.road_type)} • 
                              {getDetectorClassLabel(location.processing_profile_details?.detector_class)}
                            </div>
                          </div>
                        </td>
                        <td>
                          {location.latitude && location.longitude ? (
                            <div style={{ fontSize: '12px' }}>
                              {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}
                            </div>
                          ) : (
                            <span style={{ color: '#999', fontSize: '12px' }}>Not set</span>
                          )}
                        </td>
                        <td>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            padding: '4px 8px',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: '600',
                            backgroundColor: location.active ? '#d1fae5' : '#f3f4f6',
                            color: location.active ? '#065f46' : '#6b7280'
                          }}>
                            {location.active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              onClick={() => handleEditLocation(location)}
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
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteLocation(location)}
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
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Processing Profiles Tab */}
      {activeTab === "profiles" && (
        <>
          {/* Add Profile Button */}
          <div style={{ marginBottom: '24px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button
              onClick={() => setShowProfileForm(true)}
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
              + Add New Profile
            </button>

            <button
              onClick={fetchProcessingProfiles}
              style={{
                padding: '12px 24px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                color: '#374151',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '16px'
              }}
            >
              🔄 Refresh Profiles
            </button>
          </div>

          {/* Profile Form - THIS IS THE MISSING PART */}
          {showProfileForm && (
            <div className="dashboard-card" style={{ marginBottom: '24px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>
                {editingProfile ? 'Edit Processing Profile' : 'Add New Processing Profile'}
              </h2>

              <form onSubmit={handleProfileSubmit}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Internal Name *
                    </label>
                    <input
                      type="text"
                      name="name"
                      value={profileFormData.name}
                      onChange={handleProfileInputChange}
                      required
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px'
                      }}
                      placeholder="e.g., baliwasan_yjunction"
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Display Name *
                    </label>
                    <input
                      type="text"
                      name="display_name"
                      value={profileFormData.display_name}
                      onChange={handleProfileInputChange}
                      required
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px'
                      }}
                      placeholder="e.g., Baliwasan Y-Junction Detector"
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                    Description
                  </label>
                  <textarea
                    name="description"
                    value={profileFormData.description}
                    onChange={handleProfileInputChange}
                    rows="3"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px',
                      resize: 'vertical'
                    }}
                    placeholder="Description of this processing profile..."
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Road Type *
                    </label>
                    <select
                      name="road_type"
                      value={profileFormData.road_type}
                      onChange={handleProfileInputChange}
                      required
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px',
                        backgroundColor: 'white'
                      }}
                    >
                      {roadTypes.map(roadType => (
                        <option key={roadType.value} value={roadType.value}>
                          {roadType.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                      Detector Class *
                    </label>
                    <select
                      name="detector_class"
                      value={profileFormData.detector_class}
                      onChange={handleProfileInputChange}
                      required
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        border: '1px solid #d1d5db',
                        borderRadius: '4px',
                        fontSize: '14px',
                        backgroundColor: 'white'
                      }}
                    >
                      {detectorClasses.map(detectorClass => (
                        <option key={detectorClass.value} value={detectorClass.value}>
                          {detectorClass.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* THIS PART WAS MISSING IN THE SNIPPET */}
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
                    Detector Module
                  </label>
                  <input
                    type="text"
                    name="detector_module"
                    value={profileFormData.detector_module}
                    onChange={handleProfileInputChange}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      fontSize: '14px'
                    }}
                    placeholder="e.g., ml.vehicle_detector"
                  />
                  <p style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                    Python module path where the detector class is located
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
                  <input
                    type="checkbox"
                    name="active"
                    checked={profileFormData.active}
                    onChange={handleProfileInputChange}
                    style={{ marginRight: '8px' }}
                  />
                  <label style={{ fontWeight: '500' }}>Active Profile</label>
                </div>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <button
                    type="submit"
                    style={{
                      padding: '10px 20px',
                      border: 'none',
                      borderRadius: '4px',
                      backgroundColor: '#10b981',
                      color: 'white',
                      cursor: 'pointer',
                      fontWeight: '500'
                    }}
                  >
                    {editingProfile ? 'Update Profile' : 'Create Profile'}
                  </button>

                  <button
                    type="button"
                    onClick={cancelProfileEdit}
                    style={{
                      padding: '10px 20px',
                      border: '1px solid #d1d5db',
                      borderRadius: '4px',
                      backgroundColor: 'white',
                      color: '#374151',
                      cursor: 'pointer'
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Processing Profiles List */}
          <div className="dashboard-card">
            <h2 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '16px' }}>
              Available Processing Profiles ({processingProfiles.length})
            </h2>
            
            {profileLoading ? (
              <div style={{ textAlign: 'center', padding: '40px' }}>
                <div style={{ fontSize: '16px', color: '#666' }}>Loading processing profiles...</div>
              </div>
            ) : processingProfiles.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                No processing profiles found. Add your first profile to get started.
              </div>
            ) : (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Display Name</th>
                      <th>Internal Name</th>
                      <th>Road Type</th>
                      <th>Detector Class</th>
                      <th>Locations</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {processingProfiles.map(profile => (
                      <tr key={profile.id}>
                        <td style={{ fontWeight: '600' }}>{profile.display_name}</td>
                        <td>
                          <code style={{ fontSize: '12px', backgroundColor: '#f3f4f6', padding: '2px 6px', borderRadius: '3px' }}>
                            {profile.name}
                          </code>
                        </td>
                        <td>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            padding: '4px 8px',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: '600',
                            backgroundColor: '#e0e7ff',
                            color: '#3730a3'
                          }}>
                            {getRoadTypeLabel(profile.road_type)}
                          </span>
                        </td>
                        <td>
                          <div style={{ fontSize: '12px', fontFamily: 'monospace' }}>
                            {profile.detector_class}
                          </div>
                          <div style={{ fontSize: '11px', color: '#666' }}>
                            {profile.detector_module}
                          </div>
                        </td>
                        <td>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            padding: '4px 8px',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: '600',
                            backgroundColor: profile.location_count > 0 ? '#f0f9ff' : '#f3f4f6',
                            color: profile.location_count > 0 ? '#0369a1' : '#6b7280'
                          }}>
                            {profile.location_count} locations
                          </span>
                        </td>
                        <td>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            padding: '4px 8px',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: '600',
                            backgroundColor: profile.active ? '#d1fae5' : '#f3f4f6',
                            color: profile.active ? '#065f46' : '#6b7280'
                          }}>
                            {profile.active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              onClick={() => handleEditProfile(profile)}
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
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteProfile(profile)}
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
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default Settings;