/**
 * React hooks for WebSocket integration
 * Provides easy-to-use hooks for real-time updates in components
 */

import { useEffect, useCallback, useRef } from 'react';
import { wsService } from '../services/WebSocketService';

/**
 * Hook for listening to notifications
 * @param {number} userId - User ID to listen to
 * @param {function} onUpdate - Callback when notification received
 * @returns {object} Connection status and helper methods
 */
export const useNotifications = (userId, onUpdate) => {
  const isConnectedRef = useRef(false);

  useEffect(() => {
    if (!userId) return;

    const handleMessage = (data) => {
      if (onUpdate) {
        onUpdate(data);
      }
    };

    const handleConnect = () => {
      isConnectedRef.current = true;
    };

    const handleDisconnect = () => {
      isConnectedRef.current = false;
    };

    wsService.connectNotifications(userId, handleMessage, handleConnect, handleDisconnect);

    return () => {
      wsService.disconnect(`notifications_${userId}`);
    };
  }, [userId, onUpdate]);

  return {
    isConnected: isConnectedRef.current,
  };
};

/**
 * Hook for listening to doctor status updates
 * @param {number} doctorId - Doctor ID to listen to
 * @param {function} onUpdate - Callback when status changes
 * @returns {object} Connection status and helper methods
 */
export const useDoctorStatus = (doctorId, onUpdate) => {
  const isConnectedRef = useRef(false);

  useEffect(() => {
    if (!doctorId) return;

    const handleMessage = (data) => {
      if (onUpdate) {
        onUpdate(data);
      }
    };

    const handleConnect = () => {
      isConnectedRef.current = true;
    };

    const handleDisconnect = () => {
      isConnectedRef.current = false;
    };

    wsService.connectDoctorStatus(doctorId, handleMessage, handleConnect, handleDisconnect);

    return () => {
      wsService.disconnect(`doctor_${doctorId}`);
    };
  }, [doctorId, onUpdate]);

  return {
    isConnected: isConnectedRef.current,
  };
};

/**
 * Hook for listening to appointment updates
 * @param {number} appointmentId - Appointment ID to listen to
 * @param {function} onUpdate - Callback when appointment changes
 * @returns {object} Connection status and helper methods
 */
export const useAppointmentUpdates = (appointmentId, onUpdate) => {
  const isConnectedRef = useRef(false);

  useEffect(() => {
    if (!appointmentId) return;

    const handleMessage = (data) => {
      if (onUpdate) {
        onUpdate(data);
      }
    };

    const handleConnect = () => {
      isConnectedRef.current = true;
    };

    const handleDisconnect = () => {
      isConnectedRef.current = false;
    };

    wsService.connectAppointmentUpdates(appointmentId, handleMessage, handleConnect, handleDisconnect);

    return () => {
      wsService.disconnect(`appointment_${appointmentId}`);
    };
  }, [appointmentId, onUpdate]);

  return {
    isConnected: isConnectedRef.current,
  };
};

/**
 * Hook for syncing doctor status across multiple tabs
 * Automatically detects and responds to status changes in other tabs
 * @param {number} doctorId - Doctor ID
 * @returns {object} Current status and update function
 */
export const useDoctorStatusSync = (doctorId) => {
  const statusRef = useRef(null);

  useEffect(() => {
    if (!doctorId) return;

    const handleStatusUpdate = (data) => {
      if (data.type === 'doctor_status_update') {
        statusRef.current = data.status;
        // Trigger local state update if needed
        window.dispatchEvent(
          new CustomEvent('doctorStatusChanged', {
            detail: { doctorId, status: data.status, event: data.event }
          })
        );
      }
    };

    wsService.connectDoctorStatus(doctorId, handleStatusUpdate);

    return () => {
      wsService.disconnect(`doctor_${doctorId}`);
    };
  }, [doctorId]);

  const updateStatus = useCallback((event, status) => {
    wsService.sendDoctorEvent(doctorId, event, { status });
  }, [doctorId]);

  return {
    currentStatus: statusRef.current,
    updateStatus,
  };
};

/**
 * Hook for appointment status synchronization
 * Keeps appointment status in sync across all pages/tabs
 * @param {number} appointmentId - Appointment ID
 * @returns {object} Current status and update function
 */
export const useAppointmentStatusSync = (appointmentId) => {
  const statusRef = useRef(null);

  useEffect(() => {
    if (!appointmentId) return;

    const handleUpdate = (data) => {
      if (data.type === 'appointment_update') {
        statusRef.current = data.status;
        window.dispatchEvent(
          new CustomEvent('appointmentStatusChanged', {
            detail: { appointmentId, status: data.status }
          })
        );
      }
    };

    wsService.connectAppointmentUpdates(appointmentId, handleUpdate);

    return () => {
      wsService.disconnect(`appointment_${appointmentId}`);
    };
  }, [appointmentId]);

  const updateStatus = useCallback((status) => {
    wsService.sendAppointmentStatusUpdate(appointmentId, status);
  }, [appointmentId]);

  return {
    currentStatus: statusRef.current,
    updateStatus,
  };
};

/**
 * Hook for listening to custom events dispatched by WebSocket updates
 * @param {string} eventName - Event name to listen to
 * @param {function} listener - Callback function for the event
 */
export const useWebSocketEvent = (eventName, listener) => {
  useEffect(() => {
    if (!eventName || !listener) return;

    const handleEvent = (e) => {
      listener(e.detail);
    };

    window.addEventListener(eventName, handleEvent);

    return () => {
      window.removeEventListener(eventName, handleEvent);
    };
  }, [eventName, listener]);
};

/**
 * Hook for managing disconnection on component unmount
 */
export const useWebSocketCleanup = () => {
  useEffect(() => {
    return () => {
      // Cleanup all connections when component unmounts
      wsService.disconnectAll();
    };
  }, []);
};

export default {
  useNotifications,
  useDoctorStatus,
  useAppointmentUpdates,
  useDoctorStatusSync,
  useAppointmentStatusSync,
  useWebSocketEvent,
  useWebSocketCleanup,
};
