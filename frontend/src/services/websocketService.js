  //src/services/websocketService.js
  class WebSocketService {
    constructor() {
      this.socket = null;
      this.videoCallbacks = new Map();
      this.reconnectAttempts = 0;
      this.maxReconnectAttempts = 5;
    }

    connectToVideoProgress(videoId, onProgress, onComplete) {
      const wsUrl = `ws://127.0.0.1:8000/ws/video-progress/${videoId}/`;
      
      try {
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onopen = () => {
          console.log('WebSocket connected for video progress');
          this.reconnectAttempts = 0;
        };
        
        this.socket.onmessage = (event) => {
          const data = JSON.parse(event.data);
          
          if (data.type === 'progress_update' && onProgress) {
            onProgress(data.progress, data.message);
          } else if (data.type === 'processing_complete' && onComplete) {
            onComplete(data.video_id, data.message);
          }
        };
        
        this.socket.onclose = (event) => {
          console.log('WebSocket disconnected');
          this.attemptReconnect(videoId, onProgress, onComplete);
        };
        
        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
        };
        
      } catch (error) {
        console.error('WebSocket connection failed:', error);
      }
    }
    
    attemptReconnect(videoId, onProgress, onComplete) {
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => {
          console.log(`Attempting reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
          this.connectToVideoProgress(videoId, onProgress, onComplete);
        }, 3000);
      }
    }
    
    disconnect() {
      if (this.socket) {
        this.socket.close();
        this.socket = null;
      }
    }
  }

  export default new WebSocketService();