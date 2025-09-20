// src/pages/Settings.js
import React, { useState } from "react";

function Settings() {
  const [darkMode, setDarkMode] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const [language, setLanguage] = useState("en");

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">Traffic Monitor</h1>
        <p className="text-gray-600">Manage your account and system information</p>
      </header>

      <div className="dashboard-card mb-8">
        <h2 className="section-title">Account Information</h2>
        
        <div className="table-container mb-6">
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
          <ul className="info-text list-disc pl-5 space-y-2">
            <li><strong>Viewing Traffic Data</strong> - The Overview page displays weekly traffic patterns and daily vehicle counts. Data is collected automatically from our traffic cameras.</li>
            <li><strong>Analyzing Congestion</strong> - The Congestion Results page shows peak traffic hours for specific areas. Use this data to identify problem areas and optimize traffic flow.</li>
          </ul>
        </div>

        <div className="divider"></div>

        <h3 className="text-lg font-medium mb-4">Developers</h3>
        <p className="text-gray-600 mb-6">Developed by Students of Western Mindanao State University (WMSU)</p>

        <div className="divider"></div>

        <h3 className="text-lg font-medium mb-4">Session</h3>
        <p className="text-gray-600">Logged in as Administrator</p>
      </div>

      <div className="dashboard-card">
        <h2 className="section-title">System Settings</h2>
        
        <div className="flex items-center justify-between border-b py-4">
          <div>
            <p className="font-medium">Dark Mode</p>
            <p className="text-sm text-gray-600">Switch between light and dark themes</p>
          </div>
          <label className="inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={darkMode}
              onChange={() => setDarkMode(!darkMode)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:bg-blue-600 relative">
              <span className="absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition peer-checked:translate-x-5"></span>
            </div>
          </label>
        </div>

        <div className="flex items-center justify-between border-b py-4">
          <div>
            <p className="font-medium">Notifications</p>
            <p className="text-sm text-gray-600">Receive alerts for traffic events</p>
          </div>
          <input
            type="checkbox"
            checked={notifications}
            onChange={() => setNotifications(!notifications)}
            className="w-5 h-5"
          />
        </div>

        <div className="flex items-center justify-between py-4">
          <div>
            <p className="font-medium">Language</p>
            <p className="text-sm text-gray-600">Interface language preference</p>
          </div>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="border rounded p-2"
          >
            <option value="en">English</option>
            <option value="ph">Filipino</option>
            <option value="es">Spanish</option>
          </select>
        </div>

        <div className="mt-6 text-center">
          <button className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

export default Settings;