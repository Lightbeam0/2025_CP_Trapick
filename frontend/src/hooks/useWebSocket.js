// src/hooks/useWebSocket.js
import { useRef, useCallback, useEffect, useState } from 'react';

// Global singleton WebSocket instance (shared across all components)
let globalWebSocket = null;
let connectionCallbacks = new Set(); // To notify all components of status changes

const WEBSOCKET_URL = (() => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = process.env.NODE_ENV === 'development'
    ? '127.0.0.1:8000'
    : window.location.host;
  return `${protocol}//${host}/ws/progress/`;
})();

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

  // Keep callbacks up to date
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
    // Register this component's callback
    connectionCallbacks.add(handleStatusChange);
    console.log('✅ Registered WebSocket callback');

    // Connect if not already connected
    const ws = createWebSocket();

    // Sync current status
    if (ws.readyState === WebSocket.OPEN) {
      setConnectionStatus('connected');
    } else if (ws.readyState === WebSocket.CONNECTING) {
      setConnectionStatus('connecting');
    }

    return () => {
      // Unregister on unmount
      connectionCallbacks.delete(handleStatusChange);
      console.log('❌ Unregistered WebSocket callback');

      // Only close global socket if no one is using it
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