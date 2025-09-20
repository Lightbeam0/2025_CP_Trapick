// src/components/Sidebar.js
import React from "react";
import { Link, useLocation } from "react-router-dom";

function Sidebar() {
  const location = useLocation();

  return (
    <div className="sidebar w-64 bg-gray-800 text-white fixed h-full overflow-y-auto">
      {/* Logo/Header Section */}
      <div className="p-5 border-b border-gray-700 bg-gray-900">
        <h1 className="text-xl font-bold">Traffic Monitor</h1>
      </div>
      
      {/* System Status */}
      <div className="p-4 border-b border-gray-700 bg-green-600">
        <div className="flex items-center">
          <div className="w-3 h-3 bg-white rounded-full mr-2"></div>
          <span className="text-sm font-medium">System Operational</span>
        </div>
      </div>

      {/* Navigation Menu */}
      <nav className="p-4">
        <div className="mb-6">
          <h3 className="text-xs uppercase text-gray-400 font-semibold mb-3">Use</h3>
          <ul className="space-y-2">
            <li>
              <Link
                to="/congested"
                className={`flex items-center p-2 rounded transition-colors ${
                  location.pathname === "/congested"
                    ? "bg-blue-600 text-white"
                    : "text-gray-300 hover:bg-gray-700"
                }`}
              >
                <span className="mr-3">🚦</span>
                <span>Congested Roads</span>
              </Link>
            </li>
            <li>
              <Link
                to="/vehicles"
                className={`flex items-center p-2 rounded transition-colors ${
                  location.pathname === "/vehicles"
                    ? "bg-blue-600 text-white"
                    : "text-gray-300 hover:bg-gray-700"
                }`}
              >
                <span className="mr-3">🚗</span>
                <span>Vehicle Passing</span>
              </Link>
            </li>
          </ul>
        </div>

        <div>
          <h3 className="text-xs uppercase text-gray-400 font-semibold mb-3">Settings</h3>
          <ul className="space-y-2">
            <li>
              <Link
                to="/settings"
                className={`flex items-center p-2 rounded transition-colors ${
                  location.pathname === "/settings"
                    ? "bg-blue-600 text-white"
                    : "text-gray-300 hover:bg-gray-700"
                }`}
              >
                <span className="mr-3">⚙️</span>
                <span>Settings</span>
              </Link>
            </li>
          </ul>
        </div>
      </nav>

      {/* Quick Stats Footer */}
      <div className="absolute bottom-0 w-full p-4 bg-gray-900 border-t border-gray-700">
        <div className="grid grid-cols-3 gap-2 text-center mb-3">
          <div>
            <div className="text-lg font-bold">12</div>
            <div className="text-xs text-gray-400">Congested</div>
          </div>
          <div>
            <div className="text-lg font-bold">54.2k</div>
            <div className="text-xs text-gray-400">Vehicles</div>
          </div>
          <div>
            <div className="text-lg font-bold">8:00</div>
            <div className="text-xs text-gray-400">Peak</div>
          </div>
        </div>
        
        <div className="text-xs text-gray-400 text-center">
          <p>+2 from yesterday</p>
          <p>+5.2% from last week</p>
          <p>+1:25 longer than average</p>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;