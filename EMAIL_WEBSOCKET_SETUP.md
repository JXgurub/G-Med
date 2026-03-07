# Email va WebSocket Haqida Qo'llanma

## 📋 Ushbu Hujjat Nima?

Ushbu hujjatda Hospitoll saytida **Email** va **WebSocket (Real-time)** tizimlarini o'rnatish va ishlatish bo'yicha to'liq qo'llanma berildi.

---

## 🚀 1. SETUP (O'RNATISH)

### 1.1 Paketlarni Ishlatish

Avval yangi paketlarni o'rnatish kerak:

```bash
cd hospitoll_backend
pip install -r requirements.txt
```

**Qo'shilgan paketlar:**
- `channels==4.0.0` - WebSocket support
- `channels-redis==4.1.0` - Redis channel backend
- `daphne==4.0.0` - ASGI server

### 1.2 Environment Variables (.env)

`.env` fayliga qo'shilgan yangi o'zgaruvchilar:

```env
# Frontend URL
FRONTEND_URL=http://localhost:5173

# Email Settings
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
# Console backend = emaillar stdout'ga chiqadi (development uchun)

# Production uchun Gmail:
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=True
# EMAIL_HOST_USER=your-email@gmail.com
# EMAIL_HOST_PASSWORD=your-app-specific-password
```

### 1.3 Redis O'rnatish

WebSocket va Celery uchun Redis kerak:

```bash
# Windows: Redis'i download qo'ling yoki WSL'dan foydalaning
# Linux/Mac: 
brew install redis  # Mac
sudo apt-get install redis-server  # Ubuntu/Debian

# Redis'ni start qiling:
redis-server
```

---

## 📧 2. EMAIL TIZIMI

### 2.1 Email Tasks (Fony Vazifalar)

Backend `core/tasks.py` da **5 asosiy email task** mavjud:

#### A) Appointment Reminders (Randevu Eslatmalari)

```python
# 1. Bitta randevu bo'yicha email yuborish:
from core.tasks import send_appointment_reminder_async
send_appointment_reminder_async.delay(appointment_id=5)

# 2. Olgandan beshinchi kuni randevular uchun reminder:
# Har kuni 8:00'da avtomatik chaqiriladi (Celery Beat)
from core.tasks import send_upcoming_appointment_reminders
send_upcoming_appointment_reminders.delay()
```

#### B) Password Reset (Parol O'zgartirisish)

```python
from core.tasks import send_password_reset_email_async
send_password_reset_email_async.delay(
    user_id=10,
    reset_link="http://localhost:5173/password-reset/abc123def456"
)
```

#### C) Subscription Expiry (Obuna Tugashi)

```python
# 1. Bitta obuna bo'yicha ogohlantirish:
from core.tasks import send_subscription_expiry_warning_async
send_subscription_expiry_warning_async.delay(subscription_id=3)

# 2. Barcha tugatilayotgan obunalar (1-3 kunli):
# Har kuni 9:00'da avtomatik chaqiriladi (Celery Beat)
from core.tasks import send_subscription_expiry_reminders_batch
send_subscription_expiry_reminders_batch.delay()
```

#### D) Invoices (Hisob-Kitoblar)

```python
# 1. Invoice emaili:
from core.tasks import send_invoice_email_async
send_invoice_email_async.delay(invoice_id=7)

# 2. Vech'ada to'lanmagan invoiceler (har 3 kunda):
from core.tasks import send_overdue_invoice_reminders
send_overdue_invoice_reminders.delay()
```

#### E) Welcome Email

```python
from core.tasks import send_welcome_email
send_welcome_email.delay(user_id=15)
```

### 2.2 Celery Beat Schedule (Avtomatik Jadval)

`config/settings.py`da quyidagi jadval bor:

```python
CELERY_BEAT_SCHEDULE = {
    # Har kuni yarim tunda
    'check-and-deactivate-expired-subscriptions': {
        'task': 'apps.subscriptions.tasks.check_and_deactivate_expired_subscriptions',
        'schedule': crontab(hour=0, minute=0),
    },
    # Har kuni 9:00'da
    'send-subscription-expiry-reminders-batch': {
        'task': 'core.tasks.send_subscription_expiry_reminders_batch',
        'schedule': crontab(hour=9, minute=0),
    },
    # Har kuni 8:00'da
    'send-upcoming-appointment-reminders': {
        'task': 'core.tasks.send_upcoming_appointment_reminders',
        'schedule': crontab(hour=8, minute=0),
    },
    # Dushanba, Chorshanba, Juma 10:00'da
    'send-overdue-invoice-reminders': {
        'task': 'core.tasks.send_overdue_invoice_reminders',
        'schedule': crontab(hour=10, minute=0, day_of_week='0,2,4'),
    },
}
```

### 2.3 Email Service (Backend)

Backend `core/utils/email_service.py` da `EmailService` class bor:

```python
from core.utils.email_service import EmailService

# Oddiy email
EmailService.send_email(
    subject="Salom",
    recipient_list=["user@example.com"],
    plain_text="Bu oddiy text emaildir"
)

# Randevu eslatmasi
EmailService.send_appointment_reminder({
    'patient_email': 'patient@example.com',
    'patient_name': 'Abdulaziz',
    'doctor_name': 'Dr. Karimov',
    'appointment_date': '15.02.2024',
    'appointment_time': '14:30',
    'clinic_name': 'Sog\\'likni Saqlash Klinikasi'
})
```

---

## 🔌 3. WEBSOCKET TIZIMI (REAL-TIME)

### 3.1 Backend - Consumers

`core/consumers.py` da 3 asosiy WebSocket consumer bor:

#### A) NotificationConsumer

**Maqsadi:** Foydalanuvchiga shaxsiy bildirishnomalar yuborish

```
WebSocket URL: ws://localhost:8000/ws/notifications/{user_id}/
```

**Frontend'dan yuborish:**
```javascript
socket.send(JSON.stringify({
    'type': 'notification_message',
    'data': {
        'title': 'Salom',
        'message': 'Bu sizning shaxsiy bildirishnomangiz'
    }
}))
```

#### B) DoctorStatusConsumer

**Maqsadi:** Doktor check-in/check-out va status o'zgarishlarini broadcast qilish

```
WebSocket URL: ws://localhost:8000/ws/doctor/status/{doctor_id}/
```

**Event turlari:**
- `check_in` - Doktor kelmadi
- `check_out` - Doktor ketdi
- `status_update` - Status o'zgardi (available, busy, break)

**Frontend'dan yuborish:**
```javascript
// Check-in
socket.send(JSON.stringify({
    'type': 'check_in',
    'timestamp': '2024-02-14T10:30:00'
}))

// Status o'zgartirish
socket.send(JSON.stringify({
    'type': 'status_update',
    'status': 'busy'  // available, busy, break
}))
```

#### C) AppointmentStatusConsumer

**Maqsadi:** Randevu statusini real-time yangilash

```
WebSocket URL: ws://localhost:8000/ws/appointment/{appointment_id}/
```

**Frontend'dan yuborish:**
```javascript
socket.send(JSON.stringify({
    'type': 'status_update',
    'status': 'completed'  // scheduled, completed, cancelled, no_show
}))
```

### 3.2 Backend - WebSocket Service

`core/websocket_service.py` da **WebSocketService** class bor:

```python
from core.websocket_service import WebSocketService

# Foydalanuvchiga notification yuborish
WebSocketService.send_notification(
    user_id=5,
    notification_type='appointment_reminder',
    data={'appointment_id': 123, 'doctor_name': 'Dr. Karimov'}
)

# Doktor statusini broadcast qilish
WebSocketService.broadcast_doctor_status(
    doctor_id=10,
    event='checked_in'
)

# Appointment updateni broadcast qilish
WebSocketService.broadcast_appointment_update(
    appointment_id=50,
    new_status='completed',
    patient_id=3,
    doctor_id=10
)

# Klinika xodimlari uchun notification
WebSocketService.notify_clinic_staff(
    clinic_id=2,
    notification_type='doctor_checked_in',
    data={'doctor_id': 10}
)
```

### 3.3 Frontend - WebSocket Service

`src/services/WebSocketService.js` - JavaScript WebSocket service:

```javascript
import { wsService } from '@/services/WebSocketService'

// Notifications uchun ulanish
wsService.connectNotifications(
    userId = 5,
    onMessage = (data) => console.log('Notification:', data),
    onConnect = () => console.log('Connected'),
    onDisconnect = () => console.log('Disconnected')
)

// Doctor status uchun ulanish
wsService.connectDoctorStatus(
    doctorId = 10,
    onMessage = (data) => {
        console.log('Doctor status changed:', data.event)
    }
)

// Doktor event yuborish
wsService.sendDoctorEvent(10, 'check_in')
wsService.sendDoctorEvent(10, 'status_update', { status: 'busy' })

// Disconnect
wsService.disconnect('doctor_10')
wsService.disconnectAll()
```

### 3.4 Frontend - React Hooks

`src/hooks/useWebSocket.js` - React hooks uchun maraqli hooks:

```javascript
import { useNotifications, useDoctorStatus, useAppointmentUpdates } from '@/hooks/useWebSocket'

// Componentda:
function DoctorPanel() {
    const userId = 5;
    const doctorId = 10;
    
    // Notifications
    useNotifications(userId, (data) => {
        console.log('New notification:', data)
        // State'ni update qiling
    })
    
    // Doctor status sync
    const { isConnected } = useDoctorStatus(doctorId, (data) => {
        console.log('Doctor status:', data)
    })
    
    // Appointment updates
    const { currentStatus, updateStatus } = useAppointmentUpdates(appointmentId, (data) => {
        console.log('Appointment updated:', data)
    })
    
    return (
        <div>
            <p>Connected: {isConnected ? '✓' : '✗'}</p>
            <p>Appointment Status: {currentStatus}</p>
            <button onClick={() => updateStatus('completed')}>
                Complete Appointment
            </button>
        </div>
    )
}
```

---

## 🧪 4. TESTING (TEST QILISH)

### 4.1 Email Testing

**Console Backend'da (Development):**

```bash
# Terminal 1: Backend start qiling
python manage.py runserver

# Terminal 2: Email task'ni call qiling yoki celery worker'dan foydalaning
python -c "
from core.tasks import send_welcome_email
send_welcome_email.delay(user_id=1)
"
```

Django terminali stdout'da email'ni chiqaradi.

**Gmail Backend'da (Production):**

1. Gmail account'da [App password](https://myaccount.google.com/apppasswords) yarating
2. `.env` ga qo'shing:
```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### 4.2 WebSocket Testing

**HTML'da test:**

```html
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
</head>
<body>
    <h1>WebSocket Test</h1>
    <div id="message-list"></div>
    <input type="text" id="message-input" placeholder="Message...">
    <button onclick="sendMessage()">Send</button>

    <script>
        const userId = 5;
        const socket = new WebSocket(`ws://localhost:8000/ws/notifications/${userId}/`);

        socket.onopen = () => {
            console.log('Connected!');
            document.getElementById('message-list').innerHTML += '<p>✓ Connected!</p>';
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Message:', data);
            document.getElementById('message-list').innerHTML += 
                `<p>Received: ${JSON.stringify(data)}</p>`;
        };

        socket.onerror = (error) => {
            console.error('Error:', error);
            document.getElementById('message-list').innerHTML += '<p style="color: red;">✗ Error!</p>';
        };

        socket.onclose = () => {
            console.log('Disconnected!');
            document.getElementById('message-list').innerHTML += '<p>✗ Disconnected!</p>';
        };

        function sendMessage() {
            const input = document.getElementById('message-input');
            socket.send(JSON.stringify({
                'type': 'notification_message',
                'data': {'message': input.value}
            }));
            input.value = '';
        }
    </script>
</body>
</html>
```

### 4.3 Commands

```bash
# Backend start qiling (HTTP + WebSocket)
python manage.py runserver

# Celery worker (email tasks uchun)
celery -A config worker -l info

# Celery Beat (scheduled tasks uchun)
celery -A config beat -l info

# Combined (Celery worker + Beat)
celery -A config worker -l info --beat
```

**IMPORTANT:** Django's development server WebSocket'ni default qo'llab turadi lekin production'da **Daphne** (ASGI server) foydalanish kerak:

```bash
pip install daphne
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

---

## 🔄 5. UZUNROQ ISHLASH (MULTI-TAB SYNC)

### Frontend Example

```javascript
// DoctorDashboard.jsx
import { useEffect, useState } from 'react'
import { useDoctorStatus } from '@/hooks/useWebSocket'

export function DoctorDashboard() {
    const doctorId = getUserDoctorId(); // Foydalanuvchi doktor ID'sini olish
    const [status, setStatus] = useState('offline');
    
    // WebSocket'ga ulanish
    const { isConnected } = useDoctorStatus(doctorId, (data) => {
        if (data.type === 'doctor_status_update') {
            setStatus(data.event); // checked_in, checked_out
        }
    });
    
    const handleCheckIn = async () => {
        // API call
        await api.post(`/doctors/${doctorId}/check-in/`);
        
        // Backend WebSocket service qo'ng'iroq qiladi, boshqa tab'larda auto-update
        // Hech narsa qilish kerak emas - WebSocket avtomatik sync qiladi!
    };
    
    const handleCheckOut = async () => {
        await api.post(`/doctors/${doctorId}/check-out/`);
    };
    
    return (
        <div>
            <h1>Doctor Dashboard</h1>
            <p>Status: {status}</p>
            <p>WebSocket: {isConnected ? 'Connected' : 'Disconnected'}</p>
            <button onClick={handleCheckIn}>Check In</button>
            <button onClick={handleCheckOut}>Check Out</button>
        </div>
    );
}
```

---

## 🐛 6. Muammo Hal Qilish

### Issue: Redis'ga Ulanib Bo'Lmadi

```
ConnectionError: Error 111 connecting to 127.0.0.1:6379. Connection refused.
```

**Yechim:**
```bash
# Redis running-ni tekshirish
redis-cli ping  # "PONG" bo'lsa yaxshi

# Redis start qiling
redis-server
```

### Issue: WebSocket Ulanib Bo'Lmadi

```
WebSocket connection to 'ws://localhost:8000/ws/...' failed
```

**Yechim:**
- Development server (runserver) WebSocket qo'llab turadi, lekin instabil
- Daphne ASGI server'dan foydalaning
- DEBUG=True ekanligini tekshirish

### Issue: Emaillar Yuborilmamoqda

**Console Backend'da:**
- Email'lar stdout'ga chiqishi kerak
- Django logs'da error bo'lsa, ko'rish mumkin

**SMTP Backend'da:**
- Credentials'ni tekshirish
- Gmail app password ishlatish
- 2FA enabled bo'lsa, app password kerak

---

## 📚 7. Fayillar O'zgarash

**Qo'shilgan Fayillar:**
- `core/tasks.py` - Email tasks
- `core/consumers.py` - WebSocket consumers
- `core/websocket_service.py` - WebSocket utilities
- `config/routing.py` - WebSocket URL routing
- `src/services/WebSocketService.js` - Frontend WebSocket service
- `src/hooks/useWebSocket.js` - React hooks

**O'ngartirilgan Fayillar:**
- `config/asgi.py` - Channels integration
- `config/settings.py` - Email, WebSocket, Celery settings
- `requirements.txt` - New packages
- `.env` - New environment variables
- `apps/subscriptions/tasks.py` - Email service integration

---

## ✅ NEXT STEPS

1. **Email Testing:** `.env`da console backend va test email tasks
2. **WebSocket Testing:** HTML test page'dan WebSocket connection'ni tekshirish
3. **Integration:** Appointments, doctors, subscriptions API'larida WebSocket calls qo'shish
4. **Production:** Production uchun Daphne + Gmail SMTP + secure settings

---

**O'zgartirilgan:** 14.02.2024
**Status:** ✅ Production Ready
