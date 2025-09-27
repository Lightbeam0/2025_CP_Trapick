// src/pages/Settings.js
import React, { useState } from "react";

function Settings() {
  const [darkMode, setDarkMode] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const [language, setLanguage] = useState("en");

  return (
    <div className="main-content">
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '32px', fontWeight: 'bold', color: '#2d3748', margin: '0 0 8px 0' }}>
          Traffic Monitor
        </h1>
        <p style={{ color: '#666' }}>Manage your account and system information</p>
      </header>

      <div className="dashboard-card" style={{ marginBottom: '32px' }}>
        <h2 className="section-title">Account Information</h2>
        
        <div className="table-container" style={{ marginBottom: '24px' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>admin</td>
                <td>admin@traffic.gov</td>
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
    </div>
  );
}

export default Settings;