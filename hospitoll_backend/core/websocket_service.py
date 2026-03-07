"""
WebSocket service utilities for sending real-time notifications.
This module provides helper functions to send notifications through WebSocket channels.
"""

import logging
from typing import Optional, Union
from uuid import UUID
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class WebSocketService:
    """Service for sending real-time notifications via WebSocket."""
    
    @staticmethod
    def send_notification(user_id: Union[int, str, UUID], notification_type: str, data: Optional[dict] = None) -> bool:
        """
        Send a notification to a specific user.
        
        Args:
            user_id: ID of the user to notify
            notification_type: Type of notification (e.g., 'appointment_reminder')
            data: Additional data to include in notification
            
        Returns:
            bool: True if successful
        """
        try:
            channel_layer = get_channel_layer()
            group_name = f'notifications_{user_id}'
            
            async_to_sync(channel_layer.group_send)(  # type: ignore[arg-type]
                group_name,
                {
                    'type': 'notification_message',
                    'data': {
                        'notification_type': notification_type,
                        'payload': data or {}
                    }
                }
            )
            logger.info(f"Notification sent to user {user_id}: {notification_type}")
            return True
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def broadcast_doctor_status(doctor_id: Union[int, str, UUID], event: str, status: Optional[str] = None) -> bool:
        """
        Broadcast doctor status update to clinic and patients.
        
        Args:
            doctor_id: ID of the doctor
            event: Event type ('checked_in', 'checked_out', 'status_changed')
            status: New status if status_changed event ('available', 'busy', 'break')
            
        Returns:
            bool: True if successful
        """
        try:
            channel_layer = get_channel_layer()
            group_name = f'doctor_status_{doctor_id}'
            
            message = {
                'type': 'doctor_status_update',
                'event': event,
                'doctor_id': doctor_id,
            }
            
            if status:
                message['status'] = status
            
            async_to_sync(channel_layer.group_send)(group_name, message)  # type: ignore[arg-type]
            logger.info(f"Doctor status update sent for doctor {doctor_id}: {event}")
            return True
        except Exception as e:
            logger.error(f"Error broadcasting doctor status: {str(e)}")
            return False
    
    @staticmethod
    def broadcast_appointment_update(
        appointment_id: Union[int, str, UUID],
        new_status: str,
        patient_id: Optional[int] = None,
        doctor_id: Optional[int] = None
    ) -> bool:
        """
        Broadcast appointment status update to involved parties.
        
        Args:
            appointment_id: ID of the appointment
            new_status: New appointment status
            patient_id: ID of the patient (optional, fetched from DB if not provided)
            doctor_id: ID of the doctor (optional, fetched from DB if not provided)
            
        Returns:
            bool: True if successful
        """
        try:
            from apps.medical.models import Appointment
            
            if patient_id is None or doctor_id is None:
                appointment = Appointment.objects.get(id=appointment_id)
                patient_id = patient_id or appointment.patient.id  # type: ignore[union-attr]
                doctor_id = doctor_id or appointment.doctor.id  # type: ignore[union-attr]
            
            channel_layer = get_channel_layer()
            group_name = f'appointment_{appointment_id}'
            
            message = {
                'type': 'appointment_update',
                'appointment_id': appointment_id,
                'status': new_status,
            }
            
            async_to_sync(channel_layer.group_send)(group_name, message)  # type: ignore[arg-type]
            WebSocketService.send_notification(
                doctor_id,
                'appointment_status_changed',
                {'appointment_id': appointment_id, 'new_status': new_status}
            )
            WebSocketService.send_notification(
                patient_id,
                'appointment_status_changed',
                {'appointment_id': appointment_id, 'new_status': new_status}
            )
            
            logger.info(f"Appointment update sent for appointment {appointment_id}: {new_status}")
            return True
        except Exception as e:
            logger.error(f"Error broadcasting appointment update: {str(e)}")
            return False
    
    @staticmethod
    def notify_clinic_staff(clinic_id: int, notification_type: str, data: Optional[dict] = None) -> bool:
        """
        Send notification to all staff in a clinic (broadcast).
        
        Args:
            clinic_id: ID of the clinic
            notification_type: Type of notification
            data: Additional data
            
        Returns:
            bool: True if successful
        """
        try:
            channel_layer = get_channel_layer()
            group_name = f'clinic_status_{clinic_id}'
            
            async_to_sync(channel_layer.group_send)(  # type: ignore[arg-type]
                group_name,
                {
                    'type': 'broadcast_message',
                    'type': notification_type,
                    'message': f'{notification_type} notification',
                    'data': data or {}
                }
            )
            logger.info(f"Clinic notification sent to clinic {clinic_id}: {notification_type}")
            return True
        except Exception as e:
            logger.error(f"Error notifying clinic staff: {str(e)}")
            return False
