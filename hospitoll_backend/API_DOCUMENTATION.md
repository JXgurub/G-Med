"""
API DOCUMENTATION GUIDE
Hospitoll Hospital Management System
"""

API_ENDPOINTS = """
API ENDPOINT DOCUMENTATION
==========================

BASE URL: /api/v1/

API DOCUMENTATION ENDPOINTS:
  GET  /schema/              - OpenAPI schema JSON
  GET  /docs/                - Swagger UI (Interactive documentation)
  GET  /redoc/               - ReDoc (Alternative API documentation)

═══════════════════════════════════════════════════════════════════════════

AUTHENTICATION ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━

POST /users/token/
  Description: Get JWT access and refresh tokens
  Request:
    {
      "email": "user@example.com",
      "password": "password123"
    }
  Success Response (200):
    {
      "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }
  Error Response (401):
    {
      "detail": "Invalid credentials"
    }

POST /users/token/refresh/
  Description: Refresh access token using refresh token
  Request:
    {
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }
  Success Response (200):
    {
      "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
    }

═══════════════════════════════════════════════════════════════════════════

CLINIC ENDPOINTS
━━━━━━━━━━━━━━━━

GET /clinics/
  Description: List all active clinics (public list for home page)
  Query Parameters:
    - page: integer (pagination)
    - page_size: integer (items per page)
    - search: string (search by name or address)
    - status: string (active, inactive, etc.)
  Success Response (200):
    {
      "count": 50,
      "next": "?page=2",
      "previous": null,
      "results": [
        {
          "id": "uuid",
          "name": "Clinic Name",
          "description": "Description",
          "address": "Address",
          "rating": 4.5,
          "total_doctors": 15,
          "services": [...]
        }
      ]
    }

POST /clinics/
  Description: Create new clinic (admin only)
  Authentication: Required (admin role)
  Request:
    {
      "owner_id": "uuid",
      "name": "Clinic Name",
      "slug": "clinic-slug",
      "registration_number": "REG123",
      "address": "Address",
      "phone_number": "+998900000000",
      "email": "clinic@example.com"
    }
  Success Response (201):
    { "id": "uuid", "name": "Clinic Name", ... }

GET /clinics/{id}/
  Description: Get clinic details with departments and services
  Success Response (200):
    {
      "id": "uuid",
      "name": "Clinic Name",
      "description": "...",
      "doctors": [
        {
          "id": "uuid",
          "name": "Dr. Name",
          "specializations": ["Cardiology", "Internal Medicine"],
          "rating": 4.8,
          "consultation_fee": 100000
        }
      ],
      "departments": [...],
      "services": [...]
    }

PUT /clinics/{id}/
  Description: Update clinic (owner or admin only)
  Authentication: Required
  Request: Same as POST

═══════════════════════════════════════════════════════════════════════════

DOCTOR ENDPOINTS
━━━━━━━━━━━━━━━━

GET /doctors/
  Description: List doctors with filtering
  Query Parameters:
    - clinic_id: uuid (filter by clinic)
    - specialization: string (filter by specialization)
    - rating_min: float (minimum rating)
    - page: integer
  Success Response (200):
    {
      "count": 200,
      "results": [
        {
          "id": "uuid",
          "name": "Dr. Name",
          "clinic": "Clinic Name",
          "specializations": ["Cardiology"],
          "rating": 4.8,
          "total_ratings": 45,
          "consultation_fee": 100000,
          "available_from": "09:00",
          "available_until": "17:00",
          "experience_years": 10
        }
      ]
    }

POST /doctors/
  Description: Register new doctor (clinic owner only)
  Authentication: Required (clinic role)
  Request:
    {
      "user_id": "uuid",
      "specializations": ["uuid1", "uuid2"],
      "license_number": "LICENSE123",
      "years_of_experience": 10,
      "consultation_fee": 100000
    }
  Success Response (201):
    {...}

GET /doctors/{id}/
  Description: Get doctor details and ratings

GET /doctors/{id}/availability/
  Description: Get doctor availability slots
  Query Parameters:
    - date_from: date
    - date_to: date
  Success Response (200):
    {
      "doctor": {...},
      "available_slots": [
        {
          "date": "2024-02-15",
          "time": "10:00",
          "status": "available"
        }
      ]
    }

GET /doctors/{id}/ratings/
  Description: Get all ratings for doctor
  Success Response (200):
    {
      "average_rating": 4.8,
      "total_ratings": 45,
      "ratings": [
        {
          "patient_name": "Patient Name",
          "rating": 5,
          "comment": "Excellent doctor",
          "date": "2024-02-10"
        }
      ]
    }

═══════════════════════════════════════════════════════════════════════════

PATIENT ENDPOINTS
━━━━━━━━━━━━━━━━

GET /patients/profile/
  Description: Get current patient profile (patient only)
  Authentication: Required (patient role)
  Success Response (200):
    {
      "id": "uuid",
      "user": {
        "email": "patient@example.com",
        "first_name": "John",
        "last_name": "Doe"
      },
      "date_of_birth": "1990-01-15",
      "gender": "male",
      "blood_type": "O+",
      "allergies": "Penicillin",
      "chronic_diseases": "None"
    }

PUT /patients/profile/
  Description: Update patient profile (patient only)
  Authentication: Required

GET /patients/medical-history/
  Description: Get patient's medical history (patient only)
  Success Response (200):
    {
      "medical_records": [
        {
          "id": "uuid",
          "doctor": "Dr. Name",
          "clinic": "Clinic Name",
          "chief_complaint": "...",
          "assessment": "...",
          "diagnoses": [
            {
              "diagnosis_name": "Hypertension",
              "certainty": "confirmed"
            }
          ],
          "prescriptions": [
            {
              "medicine": "Medicine Name",
              "dosage": "1 tablet twice daily",
              "duration": "30 days"
            }
          ],
          "date": "2024-02-10"
        }
      ]
    }

GET /patients/prescriptions/
  Description: Get patient's prescriptions (patient only)
  Success Response (200):
    {
      "prescriptions": [
        {
          "id": "uuid",
          "medicine": "Medicine Name",
          "dosage": "1 tablet twice daily",
          "doctor": "Dr. Name",
          "issued_date": "2024-02-10",
          "status": "active",
          "is_filled": false
        }
      ]
    }

═══════════════════════════════════════════════════════════════════════════

APPOINTMENT ENDPOINTS
━━━━━━━━━━━━━━━━━━━

GET /medical/appointments/
  Description: Get appointments (patient or doctor specific)
  Authentication: Required
  Query Parameters:
    - status: scheduled, completed, cancelled, no_show
    - date_from: date
    - date_to: date
  Success Response (200):
    {
      "count": 10,
      "results": [
        {
          "id": "uuid",
          "patient": "John Doe",
          "doctor": "Dr. Name",
          "clinic": "Clinic Name",
          "scheduled_date": "2024-02-20T10:00:00Z",
          "status": "scheduled",
          "consultation_fee": 100000,
          "is_paid": false
        }
      ]
    }

POST /medical/appointments/
  Description: Create new appointment (patient or clinic staff)
  Authentication: Required
  Request:
    {
      "doctor_id": "uuid",
      "clinic_id": "uuid",
      "scheduled_date": "2024-02-20T10:00:00Z",
      "reason": "Chest pain",
      "appointment_type": "consultation"
    }
  Success Response (201):
    {
      "id": "uuid",
      "status": "scheduled",
      "scheduled_date": "2024-02-20T10:00:00Z"
    }

PUT /medical/appointments/{id}/
  Description: Update appointment (patient or doctor)
  Authentication: Required

PATCH /medical/appointments/{id}/cancel/
  Description: Cancel appointment
  Success Response (200):
    {
      "id": "uuid",
      "status": "cancelled"
    }

┌─ DOCTOR ONLY ENDPOINTS ──────────────────────────────────────┐
POST /medical/records/
  Description: Create medical record (doctor only)
  Authentication: Required (doctor role)
  Request:
    {
      "patient_id": "uuid",
      "appointment_id": "uuid",
      "chief_complaint": "Chest pain",
      "vital_signs": {
        "temperature": 36.8,
        "blood_pressure": "120/80",
        "heart_rate": 72,
        "respiratory_rate": 16
      },
      "examination_findings": "...",
      "assessment": "Diagnosis assessment",
      "plan": "Treatment plan"
    }
  Success Response (201):
    { "id": "uuid", ... }

POST /medical/records/{id}/diagnoses/
  Description: Add diagnosis to medical record (doctor only)
  Request:
    {
      "diagnosis_name": "Hypertension",
      "diagnosis_code": "I10",
      "certainty": "confirmed",
      "is_primary": true
    }

POST /medical/records/{id}/prescriptions/
  Description: Add prescription to medical record (doctor only)
  Request:
    {
      "medicine_id": "uuid",
      "dosage": "1 tablet twice daily",
      "frequency": "30 days",
      "duration_days": 30,
      "instructions": "Take with food"
    }

POST /medical/records/{id}/lock/
  Description: Lock medical record (doctor only)
  Success Response (200):
    { "id": "uuid", "is_locked": true }

└────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════

PHARMACY ENDPOINTS
━━━━━━━━━━━━━━━━━

GET /pharmacies/
  Description: List all active pharmacies
  Success Response (200):
    {
      "count": 30,
      "results": [
        {
          "id": "uuid",
          "name": "Pharmacy Name",
          "address": "Address",
          "phone": "+998900000000",
          "rating": 4.6
        }
      ]
    }

GET /pharmacies/{id}/medicines/
  Description: Get medicines in stock at pharmacy
  Query Parameters:
    - search: string (medicine name)
    - page: integer
  Success Response (200):
    {
      "medicines": [
        {
          "id": "uuid",
          "name": "Medicine Name",
          "dosage": "500mg",
          "price": 25000,
          "quantity": 50,
          "is_available": true
        }
      ]
    }

PATCH /pharmacies/{id}/prescriptions/{prescrip_id}/fill/
  Description: Mark prescription as filled (pharmacy only)
  Authentication: Required (pharmacy role)
  Success Response (200):
    {
      "id": "uuid",
      "is_filled": true,
      "filled_date": "2024-02-10"
    }

═══════════════════════════════════════════════════════════════════════════

PAYMENT ENDPOINTS
━━━━━━━━━━━━━━━

POST /payments/
  Description: Create payment
  Authentication: Required
  Request:
    {
      "amount": 100000,
      "payment_method": "card",
      "payment_type": "consultation",
      "appointment_id": "uuid"
    }
  Success Response (201):
    {
      "id": "uuid",
      "status": "pending",
      "amount": 100000,
      "payment_method": "card"
    }

PATCH /payments/{id}/confirm/
  Description: Confirm payment (admin only)
  Success Response (200):
    {
      "id": "uuid",
      "status": "confirmed",
      "paid_date": "2024-02-10T10:30:00Z"
    }

═══════════════════════════════════════════════════════════════════════════

SUBSCRIPTION ENDPOINTS
━━━━━━━━━━━━━━━━━━━

GET /subscriptions/plans/
  Description: List available subscription plans
  Success Response (200):
    {
      "results": [
        {
          "id": "uuid",
          "name": "Basic",
          "price": 500000,
          "duration_days": 30,
          "features": ["Up to 10 doctors", "Basic analytics"]
        }
      ]
    }

GET /subscriptions/
  Description: Get current subscription (clinic/pharmacy owner)
  Authentication: Required
  Success Response (200):
    {
      "id": "uuid",
      "plan": "Basic",
      "status": "active",
      "start_date": "2024-01-10",
      "end_date": "2024-02-10",
      "days_remaining": 5,
      "auto_renewal": true
    }

POST /subscriptions/
  Description: Create/upgrade subscription (clinic/pharmacy owner)
  Authentication: Required
  Request:
    {
      "plan_id": "uuid"
    }
  Success Response (201):
    {
      "id": "uuid",
      "status": "trial",
      "trial_end_date": "2024-02-20"
    }

═══════════════════════════════════════════════════════════════════════════

ADMIN ENDPOINTS
━━━━━━━━━━━━━━

GET /clinics/{id}/block/
  Description: Block clinic (admin only)
  Success Response (200):
    { "id": "uuid", "is_blocked": true }

PATCH /clinics/{id}/unblock/
  Description: Unblock clinic (admin only)
  Success Response (200):
    { "id": "uuid", "is_blocked": false }

POST /subscriptions/{id}/payments/confirm/
  Description: Manually confirm subscription payment (admin only)
  Success Response (200):
    {
      "subscription_id": "uuid",
      "status": "active",
      "end_date": "2024-03-10"
    }

═══════════════════════════════════════════════════════════════════════════

COMMON ERRORS
━━━━━━━━━━━

400 Bad Request
  {
    "detail": "Invalid request data",
    "errors": {
      "field_name": ["Error message"]
    }
  }

401 Unauthorized
  {
    "detail": "Authentication credentials were not provided."
  }

403 Forbidden
  {
    "detail": "Sizga bu amalni bajarolish uchun ruxsat yo'q."
  }

404 Not Found
  {
    "detail": "Not found."
  }

409 Conflict
  {
    "detail": "Email already exists."
  }

500 Internal Server Error
  {
    "detail": "Internal server error"
  }

═══════════════════════════════════════════════════════════════════════════

PAGINATION
━━━━━━━━━

All list endpoints support pagination:
  - ?page=1         - First page
  - ?page=2         - Second page
  - ?page_size=50   - 50 items per page (default: 20)

Response includes:
  {
    "count": 100,           # Total items
    "next": "?page=2",      # Next page URL
    "previous": null,       # Previous page URL
    "results": [...]        # Items
  }

═══════════════════════════════════════════════════════════════════════════

FILTERING & SEARCHING
━━━━━━━━━━━━━━━━━━

List endpoints support:
  - ?search=query       - Search by name, email, etc.
  - ?ordering=field     - Sort by field
  - ?ordering=-field    - Sort descending
  - ?field=value        - Filter by field

Example:
  GET /doctors/?clinic_id=uuid&rating_min=4.5&ordering=-rating

═══════════════════════════════════════════════════════════════════════════

AUTHENTICATION HEADERS
━━━━━━━━━━━━━━━━━━━

All authenticated endpoints require:
  Authorization: Bearer <access_token>

Example:
  curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \\
       https://api.hospitoll.uz/api/v1/patients/profile/

═══════════════════════════════════════════════════════════════════════════
"""

print(API_ENDPOINTS)
