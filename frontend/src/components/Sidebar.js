// src/components/Sidebar.js
import React from "react";
import { Link, useLocation } from "react-router-dom";
import { FaChartLine, FaCarSide, FaTrafficLight, FaCog } from "react-icons/fa";

function Sidebar() {
  const location = useLocation();

  const menuItems = [
    { path: "/", label: "Overview", icon: <FaChartLine /> },
    { path: "/vehicles", label: "Vehicles Passing", icon: <FaCarSide /> },
    { path: "/congested", label: "Congested Roads", icon: <FaTrafficLight /> },
    { path: "/settings", label: "Settings", icon: <FaCog /> },
  ];

  return (
    <div className="sidebar w-64 bg-gray-800 text-white fixed h-full overflow-y-auto">
      <div className="p-5 border-b border-gray-700">
        <h1 className="text-xl font-bold">Traffic Monitor</h1>
        <p className="text-sm text-gray-400 mt-1">Zamboanga City</p>
      </div>

      <nav className="p-4">
        <ul className="space-y-2">
          {menuItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`flex items-center p-3 rounded-lg transition-colors duration-200 ${
                  location.pathname === item.path
                    ? "bg-blue-600 text-white shadow-md"
                    : "text-gray-300 hover:bg-gray-700 hover:text-white"
                }`}
              >
                <span className="text-lg mr-3">{item.icon}</span>
                <span className="font-medium">{item.label}</span>
                {location.pathname === item.path && (
                  <span className="ml-auto w-2 h-2 bg-white rounded-full"></span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="absolute bottom-0 w-full p-4 border-t border-gray-700">
        <div className="text-center text-xs text-gray-400">
          <p>Developed by WMSU Students</p>
          <p className="mt-1">v1.0.0</p>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
