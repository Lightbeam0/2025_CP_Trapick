// src/hooks/useWebSocket.js
import { useRef, useCallback, useEffect, useState } from 'react';
import API_CONFIG from '../config/api';

// Global singleton WebSocket instance (shared across all components)
let globalWebSocket = null;
let connectionCallbacks = new Set(); // To notify all components of status changes

// ✅ USE THE CONFIGURED WS_URL DIRECTLY
const WEBSOCKET_URL = API_CONFIG.WS_URL + '/progress/';

const createWebSocket = () => {
  if (globalWebSocket && (globalWebSocket.readyState === WebSocket.CONNECTING || globalWebSocket.readyState === WebSocket.OPEN)) {
    return globalWebSocket;
  }

  console.log('Creating new WebSocket connection to:', WEBSOCKET_URL);
  globalWebSocket = new WebSocket(WEBSOCKET_URL);

  globalWebSocket.onopen = () => {
    console.log('Global WebSocket CONNECTED');
    connectionCallbacks.forEach(cb => cb('connected'));
  };

  globalWebSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log('📨 Raw WebSocket message received:', data);
      connectionCallbacks.forEach(cb => cb('message', data));
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  };

  globalWebSocket.onclose = (event) => {
    console.log('Global WebSocket CLOSED:', event.code, event.reason);
    connectionCallbacks.forEach(cb => cb('disconnected'));
    globalWebSocket = null;

    // Auto-reconnect with exponential backoff
    if (event.code !== 1000) {
      setTimeout(() => {
        console.log('Attempting to reconnect...');
        createWebSocket();
      }, 2000);
    }
  };

  globalWebSocket.onerror = (error) => {
    console.error('WebSocket error:', error);
    connectionCallbacks.forEach(cb => cb('error'));
  };

  return globalWebSocket;
};

export const useWebSocket = ({ onMessage, onStatusChange } = {}) => {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const callbacksRef = useRef({ onMessage, onStatusChange });

  useEffect(() => {
    callbacksRef.current.onMessage = onMessage;
    callbacksRef.current.onStatusChange = onStatusChange;
  }, [onMessage, onStatusChange]);

  const handleStatusChange = useCallback((status, message) => {
    console.log(`🔄 WebSocket status change: ${status}`, message);
    setConnectionStatus(status);
    if (status === 'message') {
      callbacksRef.current.onMessage?.(message);
    } else {
      callbacksRef.current.onStatusChange?.(status);
    }
  }, []);

  useEffect(() => {
    connectionCallbacks.add(handleStatusChange);
    console.log('✅ Registered WebSocket callback');

    const ws = createWebSocket();

    if (ws.readyState === WebSocket.OPEN) {
      setConnectionStatus('connected');
    } else if (ws.readyState === WebSocket.CONNECTING) {
      setConnectionStatus('connecting');
    }

    return () => {
      connectionCallbacks.delete(handleStatusChange);
      console.log('❌ Unregistered WebSocket callback');

      if (connectionCallbacks.size === 0 && globalWebSocket) {
        console.log('No more listeners — closing WebSocket');
        globalWebSocket.close(1000, 'No active listeners');
        globalWebSocket = null;
      }
    };
  }, [handleStatusChange]);

  const sendMessage = useCallback((message) => {
    if (globalWebSocket?.readyState === WebSocket.OPEN) {
      console.log('📤 Sending WebSocket message:', message);
      globalWebSocket.send(JSON.stringify(message));
      return true;
    }
    console.warn('WebSocket not connected, cannot send:', message);
    return false;
  }, []);

  const isConnected = connectionStatus === 'connected';

  return {
    sendMessage,
    connectionStatus,
    isConnected,
    reconnect: () => {
      console.log('🔄 Manual reconnect triggered');
      if (globalWebSocket) {
        globalWebSocket.close(1006, 'Manual reconnect');
      }
    },
  };
};