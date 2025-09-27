// src/components/Sidebar.js
import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { FaChartLine, FaCarSide, FaTrafficLight, FaCog, FaUpload, FaFileAlt } from "react-icons/fa";
import VideoUploadModal from "./VideoUploadModal";

function Sidebar() {
  const location = useLocation();
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

// In the menuItems array, add:
const menuItems = [
    { path: "/", label: "Overview", icon: <FaChartLine /> },
    { path: "/vehicles", label: "Vehicles Passing", icon: <FaCarSide /> },
    { path: "/congested", label: "Congested Roads", icon: <FaTrafficLight /> },
    { path: "/analysis", label: "Analysis Results", icon: <FaFileAlt /> }, // Add this line
    { path: "/settings", label: "Settings", icon: <FaCog /> },
];  

  const handleUploadSuccess = (result) => {
    console.log("Upload successful:", result);
    setIsUploadModalOpen(false);
    // You can add a success notification here
    alert(`Video uploaded successfully! Processing ID: ${result.upload_id}`);
  };

  return (
    <>
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>Traffic Monitor</h1>
          <p>Zamboanga City</p>
        </div>

        <nav className="sidebar-nav">
          <ul className="sidebar-nav-list">
            {menuItems.map((item) => (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`sidebar-nav-link ${location.pathname === item.path ? 'active' : ''}`}
                >
                  <span className="sidebar-nav-icon">{item.icon}</span>
                  <span>{item.label}</span>
                  {location.pathname === item.path && (
                    <span style={{ marginLeft: 'auto', width: '8px', height: '8px', backgroundColor: 'white', borderRadius: '50%' }}></span>
                  )}
                </Link>
              </li>
            ))}
          </ul>

          {/* Functional Upload Button */}
          <button
            onClick={() => setIsUploadModalOpen(true)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              padding: '12px 16px',
              borderRadius: '6px',
              backgroundColor: '#10b981',
              color: 'white',
              border: 'none',
              cursor: 'pointer',
              marginTop: '16px',
              transition: 'background-color 0.2s'
            }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#059669'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#10b981'}
          >
            <FaUpload style={{ fontSize: '18px', marginRight: '12px' }} />
            <span style={{ fontWeight: '500' }}>Upload Video</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <p>Developed by WMSU Students</p>
          <p style={{ marginTop: '4px' }}>v1.0.0</p>
        </div>
      </div>

      {/* Video Upload Modal */}
      <VideoUploadModal 
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadSuccess}
      />
    </>
  );
}

export default Sidebar;