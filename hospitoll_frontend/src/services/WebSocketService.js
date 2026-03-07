/**
 * WebSocket Service for Real-time Updates
 * Handles WebSocket connections to the Hospitoll backend for real-time notifications
 */

const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_HOST = window.location.host;

class WebSocketService {
  constructor() {
    this.connections = {};
    this.messageHandlers = {};
    this.reconnectAttempts = {};
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000; // 3 seconds
  }

  /**
   * Establish a WebSocket connection for notifications
   * @param {number} userId - User ID to connect
   * @param {function} onMessage - Callback for incoming messages
   * @param {function} onConnect - Callback when connected
   * @param {function} onDisconnect - Callback when disconnected
   */
  connectNotifications(userId, onMessage, onConnect, onDisconnect) {
    const key = `notifications_${userId}`;
    
    if (this.connections[key] && this.connections[key].readyState === WebSocket.OPEN) {
      console.log(`Already connected to notifications for user ${userId}`);
      return;
    }

    try {
      const url = `${WS_PROTOCOL}//${WS_HOST}/ws/notifications/${userId}/`;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log(`Connected to notifications for user ${userId}`);
        this.reconnectAttempts[key] = 0;
        this.connections[key] = ws;
        this.setupPingInterval(ws);
        if (onConnect) onConnect();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (onMessage) onMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error(`WebSocket error for notifications (${userId}):`, error);
      };

      ws.onclose = () => {
        console.log(`Disconnected from notifications for user ${userId}`);
        delete this.connections[key];
        if (onDisconnect) onDisconnect();
        this.attemptReconnect(key, () => this.connectNotifications(userId, onMessage, onConnect, onDisconnect));
      };

      this.connections[key] = ws;
    } catch (error) {
      console.error('Error connecting to notifications WebSocket:', error);
    }
  }

  /**
   * Connect to doctor status updates
   * @param {number} doctorId - Doctor ID
   * @param {function} onMessage - Callback for status updates
   * @param {function} onConnect - Callback when connected
   * @param {function} onDisconnect - Callback when disconnected
   */
  connectDoctorStatus(doctorId, onMessage, onConnect, onDisconnect) {
    const key = `doctor_${doctorId}`;
    
    if (this.connections[key] && this.connections[key].readyState === WebSocket.OPEN) {
      console.log(`Already connected to doctor status for doctor ${doctorId}`);
      return;
    }

    try {
      const url = `${WS_PROTOCOL}//${WS_HOST}/ws/doctor/status/${doctorId}/`;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log(`Connected to doctor status for doctor ${doctorId}`);
        this.reconnectAttempts[key] = 0;
        this.connections[key] = ws;
        this.setupPingInterval(ws);
        if (onConnect) onConnect();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (onMessage) onMessage(data);
        } catch (error) {
          console.error('Error parsing doctor status message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error(`WebSocket error for doctor status (${doctorId}):`, error);
      };

      ws.onclose = () => {
        console.log(`Disconnected from doctor status for doctor ${doctorId}`);
        delete this.connections[key];
        if (onDisconnect) onDisconnect();
        this.attemptReconnect(key, () => this.connectDoctorStatus(doctorId, onMessage, onConnect, onDisconnect));
      };

      this.connections[key] = ws;
    } catch (error) {
      console.error('Error connecting to doctor status WebSocket:', error);
    }
  }

  /**
   * Connect to appointment updates
   * @param {number} appointmentId - Appointment ID
   * @param {function} onMessage - Callback for appointment updates
   * @param {function} onConnect - Callback when connected
   * @param {function} onDisconnect - Callback when disconnected
   */
  connectAppointmentUpdates(appointmentId, onMessage, onConnect, onDisconnect) {
    const key = `appointment_${appointmentId}`;
    
    if (this.connections[key] && this.connections[key].readyState === WebSocket.OPEN) {
      console.log(`Already connected to appointment ${appointmentId}`);
      return;
    }

    try {
      const url = `${WS_PROTOCOL}//${WS_HOST}/ws/appointment/${appointmentId}/`;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log(`Connected to appointment updates for appointment ${appointmentId}`);
        this.reconnectAttempts[key] = 0;
        this.connections[key] = ws;
        this.setupPingInterval(ws);
        if (onConnect) onConnect();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (onMessage) onMessage(data);
        } catch (error) {
          console.error('Error parsing appointment message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error(`WebSocket error for appointment (${appointmentId}):`, error);
      };

      ws.onclose = () => {
        console.log(`Disconnected from appointment updates for appointment ${appointmentId}`);
        delete this.connections[key];
        if (onDisconnect) onDisconnect();
        this.attemptReconnect(key, () => this.connectAppointmentUpdates(appointmentId, onMessage, onConnect, onDisconnect));
      };

      this.connections[key] = ws;
    } catch (error) {
      console.error('Error connecting to appointment WebSocket:', error);
    }
  }

  /**
   * Send a message through the WebSocket
   * @param {string} connectionKey - Identifier for the connection
   * @param {object} message - Message to send
   */
  send(connectionKey, message) {
    const ws = this.connections[connectionKey];
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(message));
      } catch (error) {
        console.error(`Error sending message on ${connectionKey}:`, error);
      }
    } else {
      console.warn(`WebSocket ${connectionKey} is not open`);
    }
  }

  /**
   * Send doctor status event (check-in, check-out, status update)
   * @param {number} doctorId - Doctor ID
   * @param {string} eventType - Event type: 'check_in', 'check_out', 'status_update'
   * @param {object} data - Additional event data
   */
  sendDoctorEvent(doctorId, eventType, data = {}) {
    const key = `doctor_${doctorId}`;
    const message = {
      type: eventType,
      ...data,
      timestamp: new Date().toISOString()
    };
    this.send(key, message);
  }

  /**
   * Send appointment status update
   * @param {number} appointmentId - Appointment ID
   * @param {string} status - New appointment status
   */
  sendAppointmentStatusUpdate(appointmentId, status) {
    const key = `appointment_${appointmentId}`;
    const message = {
      type: 'status_update',
      status: status
    };
    this.send(key, message);
  }

  /**
   * Setup periodic ping to keep connection alive
   * @param {WebSocket} ws - WebSocket connection
   */
  setupPingInterval(ws) {
    if (ws.__pingInterval) clearInterval(ws.__pingInterval);
    
    ws.__pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(JSON.stringify({
            type: 'ping'
          }));
        } catch (error) {
          console.error('Error sending ping:', error);
        }
      }
    }, 30000); // Send ping every 30 seconds
  }

  /**
   * Attempt to reconnect with exponential backoff
   * @param {string} key - Connection identifier
   * @param {function} reconnectFn - Function to call to reconnect
   */
  attemptReconnect(key, reconnectFn) {
    const attempts = this.reconnectAttempts[key] || 0;
    
    if (attempts >= this.maxReconnectAttempts) {
      console.warn(`Max reconnection attempts reached for ${key}`);
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, attempts);
    console.log(`Reconnecting ${key} in ${delay}ms (attempt ${attempts + 1}/${this.maxReconnectAttempts})`);
    
    this.reconnectAttempts[key] = attempts + 1;
    setTimeout(reconnectFn, delay);
  }

  /**
   * Disconnect from a specific connection
   * @param {string} key - Connection identifier
   */
  disconnect(key) {
    const ws = this.connections[key];
    if (ws) {
      ws.close();
      delete this.connections[key];
      delete this.reconnectAttempts[key];
    }
  }

  /**
   * Disconnect from all connections
   */
  disconnectAll() {
    Object.keys(this.connections).forEach((key) => {
      this.disconnect(key);
    });
  }

  /**
   * Check if a connection is active
   * @param {string} key - Connection identifier
   * @returns {boolean} True if connection is open
   */
  isConnected(key) {
    const ws = this.connections[key];
    return ws && ws.readyState === WebSocket.OPEN;
  }
}

// Export singleton instance
export const wsService = new WebSocketService();

export default WebSocketService;
