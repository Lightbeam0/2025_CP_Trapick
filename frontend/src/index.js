// src/index.js
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

// Import the WebSocketProvider
import { WebSocketProvider } from './contexts/WebSocketContext';

// You can keep StrictMode now — the new useWebSocket is 100% safe with it!
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <WebSocketProvider>
      <App />
    </WebSocketProvider>
  </React.StrictMode>
);

// Optional performance monitoring
reportWebVitals();