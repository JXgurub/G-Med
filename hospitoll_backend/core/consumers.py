"""
WebSocket consumers for real-time updates in Hospitoll.
Handles real-time notifications for doctors, appointments, and general updates.
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer, AsyncJsonWebsocketConsumer  # type: ignore[import-untyped]
from channels.db import database_sync_to_async  # type: ignore[import-untyped]
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for general user notifications.
    Sends real-time notifications to specific users.
    """
    
    async def connect(self):
        """Called when a new WebSocket connection is established."""
        self.user_id = self.scope['url_route']['kwargs']['user_id']  # type: ignore[index]
        self.user = await self.get_user(self.user_id)
        
        if self.user is None:
            await self.close()
            logger.warning(f"WebSocket connection attempt with invalid user_id: {self.user_id}")
            return
        
        # Create a group name for this user
        self.room_group_name = f'notifications_{self.user_id}'
        
        # Join the group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connection established for user {self.user_id}")
    
    async def disconnect(self, code: int) -> None:  # type: ignore[override]
        """Called when the WebSocket connection closes."""
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected for user {self.user_id} with code {code}")
    
    async def receive_json(self, content: dict, **kwargs) -> None:  # type: ignore[override]
        """
        Called when data is received from the WebSocket.
        
        Expected message format:
        {
            'type': 'notification_message',
            'data': {...}
        }
        """
        message_type = content.get('type')
        
        if message_type == 'ping':
            # Respond to ping to keep connection alive
            await self.send_json({
                'type': 'pong',
                'timestamp': timezone.now().isoformat()
            })
        elif message_type == 'notification_message':
            # Broadcast notification to the group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'notification_message',
                    'data': content.get('data', {})
                }
            )
    
    async def notification_message(self, event):
        """
        Handle notification messages from the group.
        This method is called when a message is sent to the group.
        """
        await self.send_json({
            'type': 'notification',
            'data': event.get('data'),
            'timestamp': timezone.now().isoformat()
        })
    
    async def broadcast_message(self, event):
        """
        Handle broadcast messages (appointment updates, doctor status, etc.)
        """
        await self.send_json({
            'type': event['type'],
            'message': event.get('message'),
            'data': event.get('data'),
            'timestamp': timezone.now().isoformat()
        })
    
    @database_sync_to_async
    def get_user(self, user_id):
        """Fetch user from database (async wrapper)."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None


class DoctorStatusConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for doctor status updates.
    Broadcasts check-in/check-out and availability changes.
    """
    
    async def connect(self):
        """Called when a new WebSocket connection is established."""
        self.doctor_id = self.scope['url_route']['kwargs']['doctor_id']  # type: ignore[index]
        self.clinic_id = await self.get_clinic_id(self.doctor_id)
        
        if self.clinic_id is None:
            await self.close()
            logger.warning(f"WebSocket connection attempt with invalid doctor_id: {self.doctor_id}")
            return
        
        # Create group names for broadcasting to clinic staff and patients
        self.doctor_group_name = f'doctor_status_{self.doctor_id}'
        self.clinic_group_name = f'clinic_status_{self.clinic_id}'
        
        # Join both groups
        await self.channel_layer.group_add(self.doctor_group_name, self.channel_name)
        await self.channel_layer.group_add(self.clinic_group_name, self.channel_name)
        
        await self.accept()
        logger.info(f"WebSocket connection established for doctor {self.doctor_id}")
    
    async def disconnect(self, code: int) -> None:  # type: ignore[override]
        """Called when the WebSocket connection closes."""
        await self.channel_layer.group_discard(self.doctor_group_name, self.channel_name)
        await self.channel_layer.group_discard(self.clinic_group_name, self.channel_name)
        logger.info(f"WebSocket disconnected for doctor {self.doctor_id}")
    
    async def receive_json(self, content: dict, **kwargs) -> None:  # type: ignore[override]
        """
        Called when data is received from the WebSocket.
        
        Expected message formats:
         - {'type': 'check_in', 'timestamp': '...'}
         - {'type': 'check_out', 'timestamp': '...'}
         - {'type': 'status_update', 'status': 'available|busy|break'}
        """
        event_type = content.get('type')
        
        if event_type == 'check_in':
            await self.channel_layer.group_send(
                self.doctor_group_name,
                {
                    'type': 'doctor_status_update',
                    'event': 'checked_in',
                    'doctor_id': self.doctor_id,
                    'timestamp': content.get('timestamp', timezone.now().isoformat())
                }
            )
            await self.channel_layer.group_send(
                self.clinic_group_name,
                {
                    'type': 'broadcast_message',
                    'type_name': 'doctor_checked_in',
                    'message': f'Doctor {self.doctor_id} checked in',
                    'data': {'doctor_id': self.doctor_id}
                }
            )
        
        elif event_type == 'check_out':
            await self.channel_layer.group_send(
                self.doctor_group_name,
                {
                    'type': 'doctor_status_update',
                    'event': 'checked_out',
                    'doctor_id': self.doctor_id,
                    'timestamp': content.get('timestamp', timezone.now().isoformat())
                }
            )
            await self.channel_layer.group_send(
                self.clinic_group_name,
                {
                    'type': 'broadcast_message',
                    'type_name': 'doctor_checked_out',
                    'message': f'Doctor {self.doctor_id} checked out',
                    'data': {'doctor_id': self.doctor_id}
                }
            )
        
        elif event_type == 'status_update':
            new_status = content.get('status', 'available')
            await self.channel_layer.group_send(
                self.doctor_group_name,
                {
                    'type': 'doctor_status_update',
                    'event': 'status_changed',
                    'doctor_id': self.doctor_id,
                    'status': new_status,
                    'timestamp': timezone.now().isoformat()
                }
            )
    
    async def doctor_status_update(self, event):
        """Handle doctor status update messages."""
        await self.send_json({
            'type': 'doctor_status_update',
            'event': event.get('event'),
            'doctor_id': event.get('doctor_id'),
            'status': event.get('status', 'unknown'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        })
    
    @database_sync_to_async
    def get_clinic_id(self, doctor_id):
        """Fetch clinic ID for doctor (async wrapper)."""
        try:
            from apps.doctors.models import Doctor
            doctor = Doctor.objects.select_related('clinic').get(id=doctor_id)
            return doctor.clinic.id if doctor.clinic else None
        except Exception as e:
            logger.error(f"Error getting clinic for doctor {doctor_id}: {str(e)}")
            return None


class AppointmentStatusConsumer(AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer for appointment status updates.
    Notifies patients and doctors about appointment changes.
    """
    
    async def connect(self):
        """Called when a new WebSocket connection is established."""
        self.appointment_id = self.scope['url_route']['kwargs']['appointment_id']  # type: ignore[index]
        appointment_data = await self.get_appointment_data(self.appointment_id)
        
        if appointment_data is None:
            await self.close()
            logger.warning(f"WebSocket connection attempt with invalid appointment_id: {self.appointment_id}")
            return
        
        self.patient_id = appointment_data['patient_id']
        self.doctor_id = appointment_data['doctor_id']
        
        # Create group name for this appointment
        self.appointment_group_name = f'appointment_{self.appointment_id}'
        self.patient_group_name = f'patient_appointments_{self.patient_id}'
        self.doctor_group_name = f'doctor_appointments_{self.doctor_id}'
        
        # Join all relevant groups
        await self.channel_layer.group_add(self.appointment_group_name, self.channel_name)
        await self.channel_layer.group_add(self.patient_group_name, self.channel_name)
        await self.channel_layer.group_add(self.doctor_group_name, self.channel_name)
        
        await self.accept()
        logger.info(f"WebSocket connection established for appointment {self.appointment_id}")
    
    async def disconnect(self, code: int) -> None:  # type: ignore[override]
        """Called when the WebSocket connection closes."""
        await self.channel_layer.group_discard(self.appointment_group_name, self.channel_name)
        await self.channel_layer.group_discard(self.patient_group_name, self.channel_name)
        await self.channel_layer.group_discard(self.doctor_group_name, self.channel_name)
        logger.info(f"WebSocket disconnected for appointment {self.appointment_id}")
    
    async def receive_json(self, content: dict, **kwargs) -> None:  # type: ignore[override]
        """
        Called when data is received from the WebSocket.
        
        Expected message formats:
         - {'type': 'status_update', 'status': 'scheduled|completed|cancelled|no_show'}
         - {'type': 'reminder_sent'}
        """
        event_type = content.get('type')
        
        if event_type == 'status_update':
            new_status = content.get('status', 'scheduled')
            await self.channel_layer.group_send(
                self.appointment_group_name,
                {
                    'type': 'appointment_update',
                    'appointment_id': self.appointment_id,
                    'status': new_status,
                    'timestamp': timezone.now().isoformat()
                }
            )
        
        elif event_type == 'reminder_sent':
            await self.channel_layer.group_send(
                self.patient_group_name,
                {
                    'type': 'broadcast_message',
                    'type_name': 'appointment_reminder',
                    'message': 'Appointment reminder sent',
                    'data': {'appointment_id': self.appointment_id}
                }
            )
    
    async def appointment_update(self, event):
        """Handle appointment update messages."""
        await self.send_json({
            'type': 'appointment_update',
            'appointment_id': event.get('appointment_id'),
            'status': event.get('status'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        })
    
    async def broadcast_message(self, event):
        """Handle broadcast messages."""
        await self.send_json({
            'type': event['type_name'],
            'message': event.get('message'),
            'data': event.get('data'),
            'timestamp': timezone.now().isoformat()
        })
    
    @database_sync_to_async
    def get_appointment_data(self, appointment_id):
        """Fetch appointment data (async wrapper)."""
        try:
            from apps.medical.models import Appointment
            appointment = Appointment.objects.select_related(
                'patient', 'doctor'
            ).get(id=appointment_id)
            return {
                'patient_id': appointment.patient.id,  # type: ignore[union-attr]
                'doctor_id': appointment.doctor.id  # type: ignore[union-attr]
            }
        except Exception as e:
            logger.error(f"Error getting appointment {appointment_id}: {str(e)}")
            return None
